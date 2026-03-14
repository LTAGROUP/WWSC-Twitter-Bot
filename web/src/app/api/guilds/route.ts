import { NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { getUserGuilds, filterAdminGuilds, isBotInGuild } from '@/lib/discord';
import { createServerClient } from '@/lib/supabase';

export async function GET(req: Request) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const url = new URL(req.url);
  const action = url.searchParams.get('action');
  const guildId = url.searchParams.get('guildId');

  // Return a single guild's DB record (no Discord API calls)
  if (action === 'guild' && guildId) {
    const supabase = createServerClient();
    const { data, error } = await supabase
      .from('guilds')
      .select('id, guild_id, guild_name, log_channel_id')
      .eq('guild_id', guildId)
      .eq('owner_id', session.userId)
      .single();
    if (error || !data) {
      return NextResponse.json({ error: 'Guild not found' }, { status: 404 });
    }
    return NextResponse.json(data);
  }

  try {
    const guilds = await getUserGuilds(session.accessToken);
    const adminGuilds = filterAdminGuilds(guilds);

    // Check which guilds have the bot installed
    const guildsWithBotStatus = await Promise.all(
      adminGuilds.map(async (guild) => ({
        ...guild,
        botInstalled: await isBotInGuild(guild.id),
      }))
    );

    // Also fetch registered guilds from DB
    const supabase = createServerClient();
    const { data: registeredGuilds } = await supabase
      .from('guilds')
      .select('guild_id')
      .eq('owner_id', session.userId);

    const registeredIds = new Set(registeredGuilds?.map((g) => g.guild_id) || []);

    const result = guildsWithBotStatus.map((g) => ({
      ...g,
      registered: registeredIds.has(g.id),
    }));

    return NextResponse.json(result);
  } catch (err) {
    console.error('Failed to fetch guilds:', err);
    return NextResponse.json({ error: 'Failed to fetch guilds' }, { status: 500 });
  }
}

// Update guild settings (e.g. log_channel_id)
export async function PATCH(req: Request) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { guildId, logChannelId } = await req.json();
  if (!guildId) {
    return NextResponse.json({ error: 'guildId required' }, { status: 400 });
  }

  const supabase = createServerClient();

  const { data: guild } = await supabase
    .from('guilds')
    .select('id, owner_id')
    .eq('guild_id', guildId)
    .single();

  if (!guild || guild.owner_id !== session.userId) {
    return NextResponse.json({ error: 'Guild not found or unauthorized' }, { status: 403 });
  }

  const { data, error } = await supabase
    .from('guilds')
    .update({ log_channel_id: logChannelId || null, updated_at: new Date().toISOString() })
    .eq('id', guild.id)
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: 'Failed to update guild' }, { status: 500 });
  }

  return NextResponse.json(data);
}

// Register a guild
export async function POST(req: Request) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { guildId, guildName } = await req.json();
  if (!guildId || !guildName) {
    return NextResponse.json({ error: 'guildId and guildName required' }, { status: 400 });
  }

  const supabase = createServerClient();
  const { data, error } = await supabase
    .from('guilds')
    .upsert(
      {
        guild_id: guildId,
        guild_name: guildName,
        owner_id: session.userId,
        updated_at: new Date().toISOString(),
      },
      { onConflict: 'guild_id' }
    )
    .select()
    .single();

  if (error) {
    console.error('Failed to register guild:', error);
    return NextResponse.json({ error: 'Failed to register guild' }, { status: 500 });
  }

  return NextResponse.json(data);
}
