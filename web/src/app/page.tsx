import { getSession } from '@/lib/auth';
import { redirect } from 'next/navigation';
import Navbar from '@/components/Navbar';

export default async function Home() {
  const session = await getSession();

  if (session) {
    redirect('/dashboard');
  }

  return (
    <>
      <Navbar user={null} />
      <main className="flex flex-col items-center justify-center min-h-[80vh] px-4">
        <h1 className="text-4xl font-bold mb-4 text-center">
          WWSC Twitter Bot
        </h1>
        <p className="text-gray-400 text-lg mb-8 text-center max-w-xl">
          Automatically post Discord messages to Twitter. Configure channels,
          filters, and multiple Twitter accounts from one dashboard.
        </p>

        <div className="flex flex-col sm:flex-row gap-4">
          <a
            href="/api/auth/login"
            className="bg-[#5865F2] text-white px-6 py-3 rounded-lg text-lg font-medium hover:bg-[#4752C4] text-center"
          >
            Login with Discord
          </a>
          <a
            href="https://discord.com/oauth2/authorize?client_id=1456871051605573669"
            target="_blank"
            rel="noopener noreferrer"
            className="bg-gray-800 text-white px-6 py-3 rounded-lg text-lg font-medium hover:bg-gray-700 border border-gray-700 text-center"
          >
            Install Bot
          </a>
        </div>

        <div className="mt-16 grid grid-cols-1 sm:grid-cols-3 gap-8 max-w-3xl w-full">
          <div className="text-center">
            <div className="text-3xl mb-2">1</div>
            <h3 className="font-semibold mb-1">Install the Bot</h3>
            <p className="text-gray-400 text-sm">
              Add the bot to your Discord server
            </p>
          </div>
          <div className="text-center">
            <div className="text-3xl mb-2">2</div>
            <h3 className="font-semibold mb-1">Connect Twitter</h3>
            <p className="text-gray-400 text-sm">
              Add your Twitter API credentials
            </p>
          </div>
          <div className="text-center">
            <div className="text-3xl mb-2">3</div>
            <h3 className="font-semibold mb-1">Configure Channels</h3>
            <p className="text-gray-400 text-sm">
              Select channels and set up filters
            </p>
          </div>
        </div>
      </main>
    </>
  );
}
