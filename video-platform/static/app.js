/* 潮汐视频 · 公共 API 封装 */
const API = {
  token: localStorage.getItem('tide_token') || '',

  async request(path, opts = {}) {
    const headers = opts.headers || {};
    if (this.token) headers['Authorization'] = 'Bearer ' + this.token;
    if (opts.json !== undefined) {
      headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.json);
    }
    const res = await fetch(path, Object.assign({}, opts, { headers }));
    let data = {};
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
    return data;
  },

  get(p) { return this.request(p); },
  post(p, json) { return this.request(p, { method: 'POST', json }); },

  async me() {
    if (!this.token) return null;
    try { return (await this.get('/api/me')).user; } catch (e) { return null; }
  },

  behavior(videoId, event, watchRatio) {
    if (!this.token) return Promise.resolve();
    return this.post('/api/behavior', {
      video_id: videoId,
      event: event,
      watch_ratio: watchRatio || 0
    }).catch(() => {});
  },

  logout() {
    return this.post('/api/logout').catch(() => {}).finally(() => {
      localStorage.removeItem('tide_token');
      this.token = '';
    });
  }
};

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
