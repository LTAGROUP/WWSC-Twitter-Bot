'use client';

import { useState } from 'react';

interface TwitterAccountFormProps {
  onSuccess: () => void;
  onCancel: () => void;
  editMode?: boolean;
  accountId?: string;
  initialAccountName?: string;
}

export default function TwitterAccountForm({
  onSuccess,
  onCancel,
  editMode = false,
  accountId,
  initialAccountName = '',
}: TwitterAccountFormProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    accountName: initialAccountName,
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
        method: editMode ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editMode ? { id: accountId, ...form } : form),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to save account');
      }

      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  const credentialFields = [
    { key: 'twitterApiKey', label: 'API Key (Consumer Key)', placeholder: editMode ? 'Leave blank to keep existing' : 'Enter API Key' },
    { key: 'twitterApiSecret', label: 'API Secret (Consumer Secret)', placeholder: editMode ? 'Leave blank to keep existing' : 'Enter API Secret' },
    { key: 'twitterBearerToken', label: 'Bearer Token', placeholder: editMode ? 'Leave blank to keep existing' : 'Enter Bearer Token' },
    { key: 'twitterAccessToken', label: 'Access Token', placeholder: editMode ? 'Leave blank to keep existing' : 'Enter Access Token' },
    { key: 'twitterAccessTokenSecret', label: 'Access Token Secret', placeholder: editMode ? 'Leave blank to keep existing' : 'Enter Access Token Secret' },
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-2 rounded text-sm">
          {error}
        </div>
      )}

      <div>
        <label className="block text-sm text-gray-300 mb-1">Account Display Name</label>
        <input
          type="text"
          value={form.accountName}
          onChange={(e) => setForm({ ...form, accountName: e.target.value })}
          placeholder="e.g. My Store Bot"
          required
          className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
        />
      </div>

      {editMode && (
        <p className="text-gray-500 text-xs">Leave all credential fields blank to keep existing credentials.</p>
      )}

      {credentialFields.map(({ key, label, placeholder }) => (
        <div key={key}>
          <label className="block text-sm text-gray-300 mb-1">{label}</label>
          <input
            type="password"
            value={form[key as keyof typeof form]}
            onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            placeholder={placeholder}
            required={!editMode}
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
          {loading ? 'Saving...' : editMode ? 'Save Changes' : 'Add Account'}
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
