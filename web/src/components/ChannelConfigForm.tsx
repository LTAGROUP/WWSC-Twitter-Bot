'use client';

import { useState, useEffect } from 'react';

interface TwitterAccount {
  id: string;
  account_name: string;
}

interface ChannelConfigFormProps {
  guildId: string;
  channelId: string;
  channelName: string;
  existingConfig?: Record<string, unknown>;
  twitterAccounts: TwitterAccount[];
  onSave: () => void;
  onCancel: () => void;
}

export default function ChannelConfigForm({
  guildId,
  channelId,
  channelName,
  existingConfig,
  twitterAccounts,
  onSave,
  onCancel,
}: ChannelConfigFormProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [config, setConfig] = useState({
    enabled: true,
    twitterAccountId: '',
    filterEnabled: true,
    filterMinLength: 0,
    filterMaxLength: 10000,
    filterRequiredKeywords: '',
    filterExcludedKeywords: '',
    filterRequireAttachments: false,
    filterExcludeBots: false,
    filterRequireEmbeds: false,
    filterCustomRegex: '',
    rateLimitHourly: 50,
    rateLimitDaily: 100,
    twitterCharLimit: 280,
    embedIncludeHashtags: false,
    embedDefaultHashtags: 'restock, instock',
    embedShortenLinks: false,
  });

  useEffect(() => {
    if (existingConfig) {
      setConfig({
        enabled: existingConfig.enabled as boolean ?? true,
        twitterAccountId: (existingConfig.twitter_account_id as string) || '',
        filterEnabled: existingConfig.filter_enabled as boolean ?? true,
        filterMinLength: existingConfig.filter_min_length as number ?? 0,
        filterMaxLength: existingConfig.filter_max_length as number ?? 10000,
        filterRequiredKeywords: (existingConfig.filter_required_keywords as string[])?.join(', ') || '',
        filterExcludedKeywords: (existingConfig.filter_excluded_keywords as string[])?.join(', ') || '',
        filterRequireAttachments: existingConfig.filter_require_attachments as boolean ?? false,
        filterExcludeBots: existingConfig.filter_exclude_bots as boolean ?? false,
        filterRequireEmbeds: existingConfig.filter_require_embeds as boolean ?? false,
        filterCustomRegex: (existingConfig.filter_custom_regex as string) || '',
        rateLimitHourly: existingConfig.rate_limit_hourly as number ?? 50,
        rateLimitDaily: existingConfig.rate_limit_daily as number ?? 100,
        twitterCharLimit: existingConfig.twitter_char_limit as number ?? 280,
        embedIncludeHashtags: existingConfig.embed_include_hashtags as boolean ?? false,
        embedDefaultHashtags: (existingConfig.embed_default_hashtags as string[])?.join(', ') || 'restock, instock',
        embedShortenLinks: existingConfig.embed_shorten_links as boolean ?? false,
      });
    }
  }, [existingConfig]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const parseList = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean);

    try {
      const res = await fetch('/api/channel-configs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          guildId,
          channelId,
          channelName,
          twitterAccountId: config.twitterAccountId || null,
          enabled: config.enabled,
          filterEnabled: config.filterEnabled,
          filterMinLength: config.filterMinLength,
          filterMaxLength: config.filterMaxLength,
          filterRequiredKeywords: parseList(config.filterRequiredKeywords),
          filterExcludedKeywords: parseList(config.filterExcludedKeywords),
          filterRequireAttachments: config.filterRequireAttachments,
          filterExcludeBots: config.filterExcludeBots,
          filterRequireEmbeds: config.filterRequireEmbeds,
          filterCustomRegex: config.filterCustomRegex || null,
          rateLimitHourly: config.rateLimitHourly,
          rateLimitDaily: config.rateLimitDaily,
          twitterCharLimit: config.twitterCharLimit,
          embedIncludeHashtags: config.embedIncludeHashtags,
          embedDefaultHashtags: parseList(config.embedDefaultHashtags),
          embedShortenLinks: config.embedShortenLinks,
        }),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.error || 'Failed to save config');
      }

      onSave();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-200 px-4 py-2 rounded text-sm">
          {error}
        </div>
      )}

      {/* Basic Settings */}
      <div className="space-y-4">
        <h3 className="text-white font-semibold border-b border-gray-700 pb-2">Basic Settings</h3>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
            className="rounded"
          />
          <span className="text-gray-300 text-sm">Enabled</span>
        </label>

        <div>
          <label className="block text-sm text-gray-300 mb-1">Twitter Account</label>
          <select
            value={config.twitterAccountId}
            onChange={(e) => setConfig({ ...config, twitterAccountId: e.target.value })}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
          >
            <option value="">Select a Twitter account...</option>
            {twitterAccounts.map((acc) => (
              <option key={acc.id} value={acc.id}>
                {acc.account_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Filter Settings */}
      <div className="space-y-4">
        <h3 className="text-white font-semibold border-b border-gray-700 pb-2">Filters</h3>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={config.filterEnabled}
            onChange={(e) => setConfig({ ...config, filterEnabled: e.target.checked })}
            className="rounded"
          />
          <span className="text-gray-300 text-sm">Enable Filters</span>
        </label>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-300 mb-1">Min Length</label>
            <input
              type="number"
              value={config.filterMinLength}
              onChange={(e) => setConfig({ ...config, filterMinLength: parseInt(e.target.value) || 0 })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-1">Max Length</label>
            <input
              type="number"
              value={config.filterMaxLength}
              onChange={(e) => setConfig({ ...config, filterMaxLength: parseInt(e.target.value) || 10000 })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm text-gray-300 mb-1">Required Keywords (comma-separated)</label>
          <input
            type="text"
            value={config.filterRequiredKeywords}
            onChange={(e) => setConfig({ ...config, filterRequiredKeywords: e.target.value })}
            placeholder="keyword1, keyword2"
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
          />
        </div>

        <div>
          <label className="block text-sm text-gray-300 mb-1">Excluded Keywords (comma-separated)</label>
          <input
            type="text"
            value={config.filterExcludedKeywords}
            onChange={(e) => setConfig({ ...config, filterExcludedKeywords: e.target.value })}
            placeholder="keyword1, keyword2"
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
          />
        </div>

        <div>
          <label className="block text-sm text-gray-300 mb-1">Custom Regex</label>
          <input
            type="text"
            value={config.filterCustomRegex}
            onChange={(e) => setConfig({ ...config, filterCustomRegex: e.target.value })}
            placeholder="Optional regex pattern"
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
          />
        </div>

        <div className="flex gap-6">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={config.filterRequireAttachments}
              onChange={(e) => setConfig({ ...config, filterRequireAttachments: e.target.checked })}
              className="rounded"
            />
            <span className="text-gray-300 text-sm">Require Attachments</span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={config.filterExcludeBots}
              onChange={(e) => setConfig({ ...config, filterExcludeBots: e.target.checked })}
              className="rounded"
            />
            <span className="text-gray-300 text-sm">Exclude Bots</span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={config.filterRequireEmbeds}
              onChange={(e) => setConfig({ ...config, filterRequireEmbeds: e.target.checked })}
              className="rounded"
            />
            <span className="text-gray-300 text-sm">Require Embeds</span>
          </label>
        </div>
      </div>

      {/* Rate Limits */}
      <div className="space-y-4">
        <h3 className="text-white font-semibold border-b border-gray-700 pb-2">Rate Limits</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-300 mb-1">Hourly Limit</label>
            <input
              type="number"
              value={config.rateLimitHourly}
              onChange={(e) => setConfig({ ...config, rateLimitHourly: parseInt(e.target.value) || 50 })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-1">Daily Limit</label>
            <input
              type="number"
              value={config.rateLimitDaily}
              onChange={(e) => setConfig({ ...config, rateLimitDaily: parseInt(e.target.value) || 100 })}
              className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
            />
          </div>
        </div>
      </div>

      {/* Embed Settings */}
      <div className="space-y-4">
        <h3 className="text-white font-semibold border-b border-gray-700 pb-2">Embed / Tweet Settings</h3>

        <div>
          <label className="block text-sm text-gray-300 mb-1">Twitter Character Limit</label>
          <input
            type="number"
            value={config.twitterCharLimit}
            onChange={(e) => setConfig({ ...config, twitterCharLimit: parseInt(e.target.value) || 280 })}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
          />
        </div>

        <div>
          <label className="block text-sm text-gray-300 mb-1">Default Hashtags (comma-separated)</label>
          <input
            type="text"
            value={config.embedDefaultHashtags}
            onChange={(e) => setConfig({ ...config, embedDefaultHashtags: e.target.value })}
            className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-white text-sm"
          />
        </div>

        <div className="flex gap-6">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={config.embedIncludeHashtags}
              onChange={(e) => setConfig({ ...config, embedIncludeHashtags: e.target.checked })}
              className="rounded"
            />
            <span className="text-gray-300 text-sm">Include Hashtags</span>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={config.embedShortenLinks}
              onChange={(e) => setConfig({ ...config, embedShortenLinks: e.target.checked })}
              className="rounded"
            />
            <span className="text-gray-300 text-sm">Shorten Links</span>
          </label>
        </div>
      </div>

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={loading}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Saving...' : 'Save Configuration'}
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
