'use client';

interface Tweet {
  id: string;
  tweet_text: string;
  tweet_id: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
  channel_configs?: {
    channel_name: string | null;
    channel_id: string;
  };
}

interface TweetHistoryTableProps {
  tweets: Tweet[];
}

export default function TweetHistoryTable({ tweets }: TweetHistoryTableProps) {
  if (tweets.length === 0) {
    return (
      <div className="text-gray-400 text-center py-8">
        No tweets posted yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left text-gray-400 py-3 px-4">Time</th>
            <th className="text-left text-gray-400 py-3 px-4">Channel</th>
            <th className="text-left text-gray-400 py-3 px-4">Tweet</th>
            <th className="text-left text-gray-400 py-3 px-4">Status</th>
          </tr>
        </thead>
        <tbody>
          {tweets.map((tweet) => (
            <tr key={tweet.id} className="border-b border-gray-800 hover:bg-gray-800/50">
              <td className="py-3 px-4 text-gray-300 whitespace-nowrap">
                {new Date(tweet.created_at).toLocaleString()}
              </td>
              <td className="py-3 px-4 text-gray-300">
                #{tweet.channel_configs?.channel_name || tweet.channel_configs?.channel_id || 'Unknown'}
              </td>
              <td className="py-3 px-4 text-gray-300 max-w-md truncate">
                {tweet.tweet_id ? (
                  <a
                    href={`https://twitter.com/i/status/${tweet.tweet_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-400 hover:underline"
                  >
                    {tweet.tweet_text.substring(0, 100)}
                    {tweet.tweet_text.length > 100 ? '...' : ''}
                  </a>
                ) : (
                  <>
                    {tweet.tweet_text.substring(0, 100)}
                    {tweet.tweet_text.length > 100 ? '...' : ''}
                  </>
                )}
              </td>
              <td className="py-3 px-4">
                <span
                  className={`inline-flex items-center px-2 py-1 rounded-full text-xs ${
                    tweet.status === 'posted'
                      ? 'bg-green-900/50 text-green-300'
                      : tweet.status === 'rate_limited'
                      ? 'bg-yellow-900/50 text-yellow-300'
                      : 'bg-red-900/50 text-red-300'
                  }`}
                  title={tweet.error_message || undefined}
                >
                  {tweet.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
