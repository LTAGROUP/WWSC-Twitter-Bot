'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Navbar from '@/components/Navbar';
import ChannelConfigForm from '@/components/ChannelConfigForm';
import Link from 'next/link';

interface Channel {
  id: string;
  name: string;
  type: number;
  position: number;
}

interface TwitterAccount {
  id: string;
  account_name: string;
}

interface ChannelConfig {
  id: string;
  channel_id: string;
  channel_name: string | null;
  enabled: boolean;
  twitter_accounts: { id: string; account_name: string } | null;
  [key: string]: unknown;
}

export default function ServerDetailPage() {
  const params = useParams();
  const guildId = params.guildId as string;

  const [channels, setChannels] = useState<Channel[]>([]);
  const [configs, setConfigs] = useState<ChannelConfig[]>([]);
  const [twitterAccounts, setTwitterAccounts] = useState<TwitterAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingChannel, setEditingChannel] = useState<Channel | null>(null);

  const fetchData = async () => {
    try {
      const [channelsRes, configsRes, accountsRes] = await Promise.all([
        fetch(`/api/guilds?action=channels&guildId=${guildId}`),
        fetch(`/api/channel-configs?guildId=${guildId}`),
        fetch('/api/twitter-accounts'),
      ]);

      // Channels come from Discord API via a separate endpoint
      // For now, we'll show configured channels and allow adding new ones
      if (configsRes.ok) {
        const configsData = await configsRes.json();
        setConfigs(configsData);
      }
      if (accountsRes.ok) {
        const accountsData = await accountsRes.json();
        setTwitterAccounts(accountsData);
      }
    } catch (err) {
      console.error('Failed to fetch data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [guildId]);

  const configuredChannelIds = new Set(configs.map((c) => c.channel_id));

  return (
    <>
      <Navbar user={null} />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center gap-4 mb-8">
          <Link href="/dashboard" className="text-gray-400 hover:text-white">
            &larr; Back
          </Link>
          <h1 className="text-2xl font-bold">Server Configuration</h1>
        </div>

        {loading ? (
          <div className="text-gray-400 text-center py-16">Loading...</div>
        ) : (
          <>
            {/* Configured Channels */}
            <section className="mb-8">
              <h2 className="text-lg font-semibold mb-4">Monitored Channels</h2>
              {configs.length === 0 ? (
                <p className="text-gray-400 text-sm mb-4">
                  No channels configured yet. Add a channel below to start monitoring.
                </p>
              ) : (
                <div className="space-y-3 mb-4">
                  {configs.map((config) => (
                    <div
                      key={config.id}
                      className="bg-gray-800 rounded-lg p-4 border border-gray-700 flex items-center justify-between"
                    >
                      <div>
                        <span className="text-white font-medium">
                          #{config.channel_name || config.channel_id}
                        </span>
                        <span className="text-gray-400 text-sm ml-3">
                          {config.twitter_accounts
                            ? `→ ${config.twitter_accounts.account_name}`
                            : 'No Twitter account assigned'}
                        </span>
                        <span
                          className={`ml-3 inline-block w-2 h-2 rounded-full ${
                            config.enabled ? 'bg-green-500' : 'bg-gray-500'
                          }`}
                        />
                      </div>
                      <button
                        onClick={() =>
                          setEditingChannel({
                            id: config.channel_id,
                            name: config.channel_name || config.channel_id,
                            type: 0,
                            position: 0,
                          })
                        }
                        className="text-blue-400 text-sm hover:text-blue-300"
                      >
                        Edit
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* Add Channel Form */}
            <section className="mb-8">
              <h2 className="text-lg font-semibold mb-4">
                {editingChannel ? `Configure #${editingChannel.name}` : 'Add Channel'}
              </h2>

              {!editingChannel ? (
                <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                  <label className="block text-sm text-gray-300 mb-2">Channel ID</label>
                  <div className="flex gap-3">
                    <input
                      id="new-channel-id"
                      type="text"
                      placeholder="Enter Discord channel ID"
                      className="flex-1 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
                    />
                    <input
                      id="new-channel-name"
                      type="text"
                      placeholder="Channel name (optional)"
                      className="flex-1 bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
                    />
                    <button
                      onClick={() => {
                        const idInput = document.getElementById('new-channel-id') as HTMLInputElement;
                        const nameInput = document.getElementById('new-channel-name') as HTMLInputElement;
                        if (idInput?.value) {
                          setEditingChannel({
                            id: idInput.value,
                            name: nameInput?.value || idInput.value,
                            type: 0,
                            position: 0,
                          });
                        }
                      }}
                      className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700"
                    >
                      Configure
                    </button>
                  </div>
                  <p className="text-gray-500 text-xs mt-2">
                    Right-click a channel in Discord → Copy Channel ID (requires Developer Mode)
                  </p>
                </div>
              ) : (
                <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
                  <ChannelConfigForm
                    guildId={guildId}
                    channelId={editingChannel.id}
                    channelName={editingChannel.name}
                    existingConfig={configs.find((c) => c.channel_id === editingChannel.id) as Record<string, unknown> | undefined}
                    twitterAccounts={twitterAccounts}
                    onSave={() => {
                      setEditingChannel(null);
                      fetchData();
                    }}
                    onCancel={() => setEditingChannel(null)}
                  />
                </div>
              )}
            </section>

            {/* Twitter accounts info */}
            {twitterAccounts.length === 0 && (
              <div className="bg-yellow-900/30 border border-yellow-700/50 rounded-lg p-4">
                <p className="text-yellow-200 text-sm">
                  You need to add a Twitter account first.{' '}
                  <Link href="/dashboard/twitter" className="text-blue-400 hover:underline">
                    Add Twitter Account
                  </Link>
                </p>
              </div>
            )}
          </>
        )}
      </main>
    </>
  );
}
