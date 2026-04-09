'use client';

import { useEffect, useState } from 'react';
import Navbar from '@/components/Navbar';
import TwitterAccountForm from '@/components/TwitterAccountForm';
import Link from 'next/link';

interface TwitterAccount {
  id: string;
  account_name: string;
  is_valid: boolean;
  last_verified_at: string | null;
  created_at: string;
}

export default function TwitterAccountsPage() {
  const [accounts, setAccounts] = useState<TwitterAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [verifying, setVerifying] = useState<string | null>(null);
  const [user, setUser] = useState<{ discordUsername: string; discordAvatar: string | null; discordId: string } | null>(null);
  const [editingAccount, setEditingAccount] = useState<TwitterAccount | null>(null);

  const fetchAccounts = async () => {
    try {
      const res = await fetch('/api/twitter-accounts');
      if (res.ok) {
        setAccounts(await res.json());
      }
    } catch (err) {
      console.error('Failed to fetch accounts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
    fetch('/api/auth/me').then((r) => r.ok && r.json()).then((d) => d && setUser(d));
  }, []);

  const verifyAccount = async (accountId: string) => {
    setVerifying(accountId);
    try {
      const res = await fetch('/api/verify-twitter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accountId }),
      });
      const data = await res.json();
      if (data.valid) {
        if (data.writeAccess === false) {
          alert(
            `Credentials valid (@${data.twitterUser?.username || 'unknown'}), but tokens only have "${data.permissionLevel}" permission.\n\n` +
            `Posting tweets requires "read-write" access.\n\n` +
            `To fix: go to the Twitter Developer Portal, ensure your app has "Read and Write" permissions, then REGENERATE your Access Token and Access Token Secret. Old tokens keep old permissions.`
          );
        } else {
          alert(`Verified! Twitter user: @${data.twitterUser?.username || 'unknown'} (${data.permissionLevel})`);
        }
      } else {
        alert(`Verification failed: ${data.error}`);
      }
      fetchAccounts();
    } catch (err) {
      alert('Failed to verify account');
    } finally {
      setVerifying(null);
    }
  };

  const deleteAccount = async (accountId: string) => {
    if (!confirm('Are you sure you want to delete this Twitter account?')) return;

    try {
      await fetch('/api/twitter-accounts', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: accountId }),
      });
      fetchAccounts();
    } catch (err) {
      alert('Failed to delete account');
    }
  };

  return (
    <>
      <Navbar user={user} />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-gray-400 hover:text-white">
              &larr; Back
            </Link>
            <h1 className="text-2xl font-bold">Twitter Accounts</h1>
          </div>
          {!showForm && !editingAccount && (
            <button
              onClick={() => setShowForm(true)}
              className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm hover:bg-blue-700"
            >
              Add Account
            </button>
          )}
        </div>

        {showForm && (
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-8">
            <h2 className="text-lg font-semibold mb-4">Add Twitter Account</h2>
            <TwitterAccountForm
              onSuccess={() => {
                setShowForm(false);
                fetchAccounts();
              }}
              onCancel={() => setShowForm(false)}
            />
          </div>
        )}

        {editingAccount && (
          <div className="bg-gray-800 rounded-lg p-6 border border-gray-700 mb-8">
            <h2 className="text-lg font-semibold mb-4">Edit: {editingAccount.account_name}</h2>
            <TwitterAccountForm
              editMode
              accountId={editingAccount.id}
              initialAccountName={editingAccount.account_name}
              onSuccess={() => {
                setEditingAccount(null);
                fetchAccounts();
              }}
              onCancel={() => setEditingAccount(null)}
            />
          </div>
        )}

        {loading ? (
          <div className="text-gray-400 text-center py-16">Loading...</div>
        ) : accounts.length === 0 && !showForm ? (
          <div className="text-center py-16">
            <p className="text-gray-400 mb-4">No Twitter accounts added yet.</p>
            <button
              onClick={() => setShowForm(true)}
              className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm hover:bg-blue-700"
            >
              Add Your First Account
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {accounts.map((account) => (
              <div
                key={account.id}
                className="bg-gray-800 rounded-lg p-6 border border-gray-700 flex items-center justify-between"
              >
                <div>
                  <h3 className="text-white font-semibold">{account.account_name}</h3>
                  <div className="flex items-center gap-3 mt-1">
                    <span
                      className={`inline-flex items-center gap-1 text-xs ${
                        account.is_valid ? 'text-green-400' : 'text-gray-500'
                      }`}
                    >
                      <span
                        className={`w-2 h-2 rounded-full ${
                          account.is_valid ? 'bg-green-500' : 'bg-gray-500'
                        }`}
                      />
                      {account.is_valid ? 'Verified' : 'Not verified'}
                    </span>
                    {account.last_verified_at && (
                      <span className="text-gray-500 text-xs">
                        Last checked: {new Date(account.last_verified_at).toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => verifyAccount(account.id)}
                    disabled={verifying === account.id}
                    className="bg-gray-700 text-gray-300 px-3 py-1 rounded text-sm hover:bg-gray-600 disabled:opacity-50"
                  >
                    {verifying === account.id ? 'Verifying...' : 'Verify'}
                  </button>
                  <button
                    onClick={() => { setEditingAccount(account); setShowForm(false); }}
                    className="bg-gray-700 text-gray-300 px-3 py-1 rounded text-sm hover:bg-gray-600"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => deleteAccount(account.id)}
                    className="bg-red-900/50 text-red-300 px-3 py-1 rounded text-sm hover:bg-red-900"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
