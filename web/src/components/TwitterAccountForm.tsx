'use client';

import { useState } from 'react';

interface TwitterAccountFormProps {
  onSuccess: () => void;
  onCancel: () => void;
}

export default function TwitterAccountForm({ onSuccess, onCancel }: TwitterAccountFormProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    accountName: '',
    twitterApiKey: '',
    twitterApiSecret: '',
    twitterBearerToken: '',
    twitterAccessToken: '',
    twitterAccessTokenSecret: '',
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const res = await fetch('/api/twitter-accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to add account');
      }

      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  const fields = [
    { key: 'accountName', label: 'Account Display Name', placeholder: 'e.g. My Store Bot' },
    { key: 'twitterApiKey', label: 'API Key (Consumer Key)', placeholder: 'Enter API Key' },
    { key: 'twitterApiSecret', label: 'API Secret (Consumer Secret)', placeholder: 'Enter API Secret' },
    { key: 'twitterBearerToken', label: 'Bearer Token', placeholder: 'Enter Bearer Token' },
    { key: 'twitterAccessToken', label: 'Access Token', placeholder: 'Enter Access Token' },
    { key: 'twitterAccessTokenSecret', label: 'Access Token Secret', placeholder: 'Enter Access Token Secret' },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-2 rounded text-sm">
          {error}
        </div>
      )}

      {fields.map(({ key, label, placeholder }) => (
        <div key={key}>
          <label className="block text-sm text-gray-300 mb-1">{label}</label>
          <input
            type={key === 'accountName' ? 'text' : 'password'}
            value={form[key as keyof typeof form]}
            onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            placeholder={placeholder}
            required
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
          />
        </div>
      ))}

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Adding...' : 'Add Account'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="bg-gray-700 text-gray-300 px-4 py-2 rounded text-sm hover:bg-gray-600"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
