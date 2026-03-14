import { NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { getUserGuilds, filterAdminGuilds, isBotInGuild } from '@/lib/discord';
import { createServerClient } from '@/lib/supabase';

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
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
