import { NextRequest, NextResponse } from 'next/server';
import { exchangeCode, getDiscordUser } from '@/lib/discord';
import { createServerClient } from '@/lib/supabase';
import { createSession } from '@/lib/auth';

export async function GET(req: NextRequest) {
  const code = req.nextUrl.searchParams.get('code');
  if (!code) {
    return NextResponse.redirect(new URL('/?error=no_code', req.url));
  }

  try {
    const tokens = await exchangeCode(code);
    const discordUser = await getDiscordUser(tokens.access_token);

    const supabase = createServerClient();

    // Upsert user
    const { data: user, error } = await supabase
      .from('users')
      .upsert(
        {
          discord_id: discordUser.id,
          discord_username: discordUser.username,
          discord_avatar: discordUser.avatar,
          updated_at: new Date().toISOString(),
        },
        { onConflict: 'discord_id' }
      )
      .select('id')
      .single();

    if (error || !user) {
      console.error('Failed to upsert user:', error);
      return NextResponse.redirect(new URL(`/?error=db_error&detail=${error?.code ?? 'no_user'}`, req.url));
    }

    await createSession({
      userId: user.id,
      discordId: discordUser.id,
      discordUsername: discordUser.username,
      discordAvatar: discordUser.avatar,
      accessToken: tokens.access_token,
    });

    return NextResponse.redirect(new URL('/dashboard', req.url));
  } catch (err) {
    console.error('OAuth callback error:', err);
    return NextResponse.redirect(new URL('/?error=auth_failed', req.url));
  }
}
