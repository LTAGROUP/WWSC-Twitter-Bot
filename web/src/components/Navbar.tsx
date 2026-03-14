'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

interface NavbarProps {
  user: {
    discordUsername: string;
    discordAvatar: string | null;
    discordId: string;
  } | null;
}

export default function Navbar({ user }: NavbarProps) {
  const pathname = usePathname();

  const navLinks = user
    ? [
        { href: '/dashboard', label: 'Servers' },
        { href: '/dashboard/twitter', label: 'Twitter Accounts' },
        { href: '/dashboard/history', label: 'Tweet History' },
      ]
    : [];

  return (
    <nav className="bg-gray-900 border-b border-gray-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-8">
            <Link href="/" className="text-white font-bold text-lg">
              WWSC Twitter Bot
            </Link>
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`text-sm ${
                  pathname === link.href
                    ? 'text-blue-400'
                    : 'text-gray-300 hover:text-white'
                }`}
              >
                {link.label}
              </Link>
            ))}
          </div>
          <div className="flex items-center gap-4">
            {user ? (
              <>
                <div className="flex items-center gap-2">
                  {user.discordAvatar && (
                    <img
                      src={`https://cdn.discordapp.com/avatars/${user.discordId}/${user.discordAvatar}.png?size=32`}
                      alt=""
                      className="w-8 h-8 rounded-full"
                    />
                  )}
                  <span className="text-gray-300 text-sm">{user.discordUsername}</span>
                </div>
                <form action="/api/auth/logout" method="POST">
                  <button
                    type="submit"
                    className="text-sm text-gray-400 hover:text-white"
                  >
                    Logout
                  </button>
                </form>
              </>
            ) : (
              <a
                href="/api/auth/login"
                className="bg-[#5865F2] text-white px-4 py-2 rounded-md text-sm hover:bg-[#4752C4]"
              >
                Login with Discord
              </a>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
