'use client';

import { useEffect, useState } from 'react';
import Navbar from '@/components/Navbar';
import TweetHistoryTable from '@/components/TweetHistoryTable';
import Link from 'next/link';

export default function HistoryPage() {
  const [tweets, setTweets] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Tweet history will be fetched from a dedicated endpoint
    // For now, show empty state
    setLoading(false);
  }, []);

  return (
    <>
      <Navbar user={null} />
      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Link href="/dashboard" className="text-gray-400 hover:text-white">
            &larr; Back
          </Link>
          <h1 className="text-2xl font-bold">Tweet History</h1>
        </div>

        <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
          {loading ? (
            <div className="text-gray-400 text-center py-16">Loading...</div>
          ) : (
            <TweetHistoryTable tweets={tweets} />
          )}
        </div>
      </main>
    </>
  );
}
