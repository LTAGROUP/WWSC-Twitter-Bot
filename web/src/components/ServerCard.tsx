'use client';

import Link from 'next/link';

interface ServerCardProps {
  guild: {
    id: string;
    name: string;
    icon: string | null;
    botInstalled: boolean;
    registered: boolean;
  };
  onRegister: (guildId: string, guildName: string) => void;
}

export default function ServerCard({ guild, onRegister }: ServerCardProps) {
  const iconUrl = guild.icon
    ? `https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png?size=64`
    : null;

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <div className="flex items-center gap-4 mb-4">
        {iconUrl ? (
          <img src={iconUrl} alt="" className="w-12 h-12 rounded-full" />
        ) : (
          <div className="w-12 h-12 rounded-full bg-gray-700 flex items-center justify-center text-gray-400 text-lg font-bold">
            {guild.name.charAt(0)}
          </div>
        )}
        <div>
          <h3 className="text-white font-semibold">{guild.name}</h3>
          <p className="text-gray-400 text-sm">ID: {guild.id}</p>
        </div>
      </div>

      <div className="flex items-center gap-2 mb-4">
        <span
          className={`inline-block w-2 h-2 rounded-full ${
            guild.botInstalled ? 'bg-green-500' : 'bg-red-500'
          }`}
        />
        <span className="text-sm text-gray-400">
          {guild.botInstalled ? 'Bot installed' : 'Bot not installed'}
        </span>
      </div>

      {!guild.botInstalled ? (
        <a
          href="https://discord.com/oauth2/authorize?client_id=1456871051605573669"
          target="_blank"
          rel="noopener noreferrer"
          className="block w-full text-center bg-[#5865F2] text-white py-2 rounded-md text-sm hover:bg-[#4752C4]"
        >
          Install Bot
        </a>
      ) : guild.registered ? (
        <Link
          href={`/dashboard/servers/${guild.id}`}
          className="block w-full text-center bg-blue-600 text-white py-2 rounded-md text-sm hover:bg-blue-700"
        >
          Manage Channels
        </Link>
      ) : (
        <button
          onClick={() => onRegister(guild.id, guild.name)}
          className="w-full bg-green-600 text-white py-2 rounded-md text-sm hover:bg-green-700"
        >
          Register Server
        </button>
      )}
    </div>
  );
}
