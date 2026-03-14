import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { createServerClient } from '@/lib/supabase';
import { encrypt } from '@/lib/encryption';

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const supabase = createServerClient();
  const { data, error } = await supabase
    .from('twitter_accounts')
    .select('id, account_name, is_valid, last_verified_at, created_at, updated_at')
    .eq('owner_id', session.userId)
    .order('created_at', { ascending: false });

  if (error) {
    return NextResponse.json({ error: 'Failed to fetch accounts' }, { status: 500 });
  }

  return NextResponse.json(data);
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const body = await req.json();
  const {
    accountName,
    twitterApiKey,
    twitterApiSecret,
    twitterBearerToken,
    twitterAccessToken,
    twitterAccessTokenSecret,
  } = body;

  if (!accountName || !twitterApiKey || !twitterApiSecret || !twitterBearerToken || !twitterAccessToken || !twitterAccessTokenSecret) {
    return NextResponse.json({ error: 'All fields are required' }, { status: 400 });
  }

  // Encrypt all credentials
  const [encApiKey, encApiSecret, encBearer, encAccess, encAccessSecret] = await Promise.all([
    encrypt(twitterApiKey),
    encrypt(twitterApiSecret),
    encrypt(twitterBearerToken),
    encrypt(twitterAccessToken),
    encrypt(twitterAccessTokenSecret),
  ]);

  const supabase = createServerClient();
  const { data, error } = await supabase
    .from('twitter_accounts')
    .insert({
      owner_id: session.userId,
      account_name: accountName,
      twitter_api_key: encApiKey,
      twitter_api_secret: encApiSecret,
      twitter_bearer_token: encBearer,
      twitter_access_token: encAccess,
      twitter_access_token_secret: encAccessSecret,
    })
    .select('id, account_name, is_valid, created_at')
    .single();

  if (error) {
    console.error('Failed to create Twitter account:', error);
    return NextResponse.json({ error: 'Failed to create account' }, { status: 500 });
  }

  return NextResponse.json(data, { status: 201 });
}

export async function DELETE(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { id } = await req.json();
  if (!id) {
    return NextResponse.json({ error: 'Account id required' }, { status: 400 });
  }

  const supabase = createServerClient();

  // Verify ownership
  const { data: account } = await supabase
    .from('twitter_accounts')
    .select('owner_id')
    .eq('id', id)
    .single();

  if (!account || account.owner_id !== session.userId) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  const { error } = await supabase
    .from('twitter_accounts')
    .delete()
    .eq('id', id);

  if (error) {
    return NextResponse.json({ error: 'Failed to delete account' }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
