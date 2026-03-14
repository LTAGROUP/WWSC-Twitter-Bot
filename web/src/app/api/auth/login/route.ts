import { NextResponse } from 'next/server';
import { getOAuthUrl } from '@/lib/discord';

export async function GET() {
  return NextResponse.redirect(getOAuthUrl());
}
