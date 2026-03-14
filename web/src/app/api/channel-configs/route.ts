import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { createServerClient } from '@/lib/supabase';

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const guildId = req.nextUrl.searchParams.get('guildId');

  const supabase = createServerClient();

  // Get user's guild UUIDs
  const { data: userGuilds } = await supabase
    .from('guilds')
    .select('id, guild_id')
    .eq('owner_id', session.userId);

  if (!userGuilds?.length) {
    return NextResponse.json([]);
  }

  const guildUuids = guildId
    ? userGuilds.filter((g) => g.guild_id === guildId).map((g) => g.id)
    : userGuilds.map((g) => g.id);

  const { data, error } = await supabase
    .from('channel_configs')
    .select('*, twitter_accounts(id, account_name)')
    .in('guild_id', guildUuids)
    .order('created_at', { ascending: false });

  if (error) {
    return NextResponse.json({ error: 'Failed to fetch configs' }, { status: 500 });
  }

  return NextResponse.json(data);
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const body = await req.json();
  const { guildId, channelId, channelName, twitterAccountId, ...settings } = body;

  if (!guildId || !channelId) {
    return NextResponse.json({ error: 'guildId and channelId required' }, { status: 400 });
  }

  const supabase = createServerClient();

  // Verify guild ownership - look up guild by Discord guild_id
  const { data: guild } = await supabase
    .from('guilds')
    .select('id, owner_id')
    .eq('guild_id', guildId)
    .single();

  if (!guild || guild.owner_id !== session.userId) {
    return NextResponse.json({ error: 'Guild not found or unauthorized' }, { status: 403 });
  }

  const configData: Record<string, unknown> = {
    guild_id: guild.id,
    channel_id: channelId,
    channel_name: channelName || null,
    twitter_account_id: twitterAccountId || null,
    enabled: settings.enabled ?? true,
    filter_enabled: settings.filterEnabled ?? true,
    filter_min_length: settings.filterMinLength ?? 0,
    filter_max_length: settings.filterMaxLength ?? 10000,
    filter_required_keywords: settings.filterRequiredKeywords ?? [],
    filter_excluded_keywords: settings.filterExcludedKeywords ?? [],
    filter_required_roles: settings.filterRequiredRoles ?? [],
    filter_allowed_users: settings.filterAllowedUsers ?? [],
    filter_require_attachments: settings.filterRequireAttachments ?? false,
    filter_exclude_bots: settings.filterExcludeBots ?? false,
    filter_require_embeds: settings.filterRequireEmbeds ?? false,
    filter_custom_regex: settings.filterCustomRegex ?? null,
    rate_limit_hourly: settings.rateLimitHourly ?? 50,
    rate_limit_daily: settings.rateLimitDaily ?? 100,
    twitter_char_limit: settings.twitterCharLimit ?? 280,
    embed_include_hashtags: settings.embedIncludeHashtags ?? false,
    embed_default_hashtags: settings.embedDefaultHashtags ?? ['restock', 'instock'],
    embed_shorten_links: settings.embedShortenLinks ?? false,
    embed_tweet_templates: settings.embedTweetTemplates ?? [],
  };

  const { data, error } = await supabase
    .from('channel_configs')
    .upsert(configData, { onConflict: 'guild_id,channel_id' })
    .select('*, twitter_accounts(id, account_name)')
    .single();

  if (error) {
    console.error('Failed to save channel config:', error);
    return NextResponse.json({ error: 'Failed to save config' }, { status: 500 });
  }

  return NextResponse.json(data);
}

export async function DELETE(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await req.json();
  if (!id) {
    return NextResponse.json({ error: 'Config id required' }, { status: 400 });
  }

  const supabase = createServerClient();

  // Verify ownership through guild
  const { data: config } = await supabase
    .from('channel_configs')
    .select('guild_id, guilds(owner_id)')
    .eq('id', id)
    .single();

  if (!config || (config as unknown as { guilds: { owner_id: string } }).guilds?.owner_id !== session.userId) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  const { error } = await supabase
    .from('channel_configs')
    .delete()
    .eq('id', id);

  if (error) {
    return NextResponse.json({ error: 'Failed to delete config' }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
