const DISCORD_API = 'https://discord.com/api/v10';
const CLIENT_ID = process.env.DISCORD_CLIENT_ID!;
const CLIENT_SECRET = process.env.DISCORD_CLIENT_SECRET!;
const REDIRECT_URI = process.env.NEXT_PUBLIC_BASE_URL
  ? `${process.env.NEXT_PUBLIC_BASE_URL}/api/auth/callback`
  : 'http://localhost:3000/api/auth/callback';

export const BOT_INVITE_URL = 'https://discord.com/oauth2/authorize?client_id=1456871051605573669';

export function getOAuthUrl(): string {
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: 'code',
    scope: 'identify guilds',
  });
  return `https://discord.com/oauth2/authorize?${params}`;
}

export async function exchangeCode(code: string): Promise<{
  access_token: string;
  refresh_token: string;
  expires_in: number;
}> {
  const res = await fetch(`${DISCORD_API}/oauth2/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
      grant_type: 'authorization_code',
      code,
      redirect_uri: REDIRECT_URI,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Discord token exchange failed: ${err}`);
  }

  return res.json();
}

export interface DiscordUser {
  id: string;
  username: string;
  avatar: string | null;
  discriminator: string;
}

export async function getDiscordUser(accessToken: string): Promise<DiscordUser> {
  const res = await fetch(`${DISCORD_API}/users/@me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error('Failed to fetch Discord user');
  return res.json();
}

export interface DiscordGuild {
  id: string;
  name: string;
  icon: string | null;
  owner: boolean;
  permissions: string;
}

export async function getUserGuilds(accessToken: string): Promise<DiscordGuild[]> {
  const res = await fetch(`${DISCORD_API}/users/@me/guilds`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error('Failed to fetch user guilds');
  return res.json();
}

// Filter guilds where user has MANAGE_GUILD permission (0x20)
export function filterAdminGuilds(guilds: DiscordGuild[]): DiscordGuild[] {
  const MANAGE_GUILD = 0x20;
  return guilds.filter(
    (g) => g.owner || (BigInt(g.permissions) & BigInt(MANAGE_GUILD)) !== BigInt(0)
  );
}

// Get channels for a guild using the bot token
export interface DiscordChannel {
  id: string;
  name: string;
  type: number;
  position: number;
}

export async function getGuildChannels(guildId: string): Promise<DiscordChannel[]> {
  const botToken = process.env.DISCORD_BOT_TOKEN;
  if (!botToken) throw new Error('DISCORD_BOT_TOKEN not configured');

  const res = await fetch(`${DISCORD_API}/guilds/${guildId}/channels`, {
    headers: { Authorization: `Bot ${botToken}` },
  });
  if (!res.ok) throw new Error('Failed to fetch guild channels');

  const channels: DiscordChannel[] = await res.json();
  // Return only text channels (type 0)
  return channels.filter((c) => c.type === 0).sort((a, b) => a.position - b.position);
}

// Check if bot is in a guild
export async function isBotInGuild(guildId: string): Promise<boolean> {
  const botToken = process.env.DISCORD_BOT_TOKEN;
  if (!botToken) return false;

  try {
    const res = await fetch(`${DISCORD_API}/guilds/${guildId}`, {
      headers: { Authorization: `Bot ${botToken}` },
    });
    return res.ok;
  } catch {
    return false;
  }
}
