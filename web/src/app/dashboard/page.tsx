'use client';

import { useEffect, useState } from 'react';
import Navbar from '@/components/Navbar';
import ServerCard from '@/components/ServerCard';

interface Guild {
  id: string;
  name: string;
  icon: string | null;
  botInstalled: boolean;
  registered: boolean;
}

export default function DashboardPage() {
  const [guilds, setGuilds] = useState<Guild[]>([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<{ discordUsername: string; discordAvatar: string | null; discordId: string } | null>(null);

  const fetchGuilds = async () => {
    try {
      const [guildsRes, meRes] = await Promise.all([
        fetch('/api/guilds'),
        fetch('/api/auth/me'),
      ]);
      if (guildsRes.status === 401) {
        window.location.href = '/api/auth/login';
        return;
      }
      const data = await guildsRes.json();
      setGuilds(data);
      if (meRes.ok) setUser(await meRes.json());
    } catch (err) {
      console.error('Failed to fetch guilds:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGuilds();
  }, []);

  const handleRegister = async (guildId: string, guildName: string) => {
    try {
      await fetch('/api/guilds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ guildId, guildName }),
      });
      fetchGuilds();
    } catch (err) {
      console.error('Failed to register guild:', err);
    }
  };

  return (
    <>
      <Navbar user={user} />
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-2xl font-bold">Your Servers</h1>
          <a
            href="https://discord.com/oauth2/authorize?client_id=1456871051605573669"
            target="_blank"
            rel="noopener noreferrer"
            className="bg-[#5865F2] text-white px-4 py-2 rounded-md text-sm hover:bg-[#4752C4]"
          >
            Install Bot to Server
          </a>
        </div>

        {loading ? (
          <div className="text-gray-400 text-center py-16">Loading servers...</div>
        ) : guilds.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-400 mb-4">
              No servers found. Make sure you have admin permissions in at least one server.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {guilds.map((guild) => (
              <ServerCard
                key={guild.id}
                guild={guild}
                onRegister={handleRegister}
              />
            ))}
          </div>
        )}
      </main>
    </>
  );
}
