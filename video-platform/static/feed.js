/* 潮汐视频 · 推荐流逻辑 */
(function () {
  const feed = document.getElementById('feed');
  const userBox = document.getElementById('userBox');
  const refreshBtn = document.getElementById('refreshBtn');
  let me = null;

  function renderUserBox() {
    if (me) {
      userBox.innerHTML =
        '<span class="uname">@' + esc(me.username) + '</span>' +
        '<a class="btn" href="javascript:void(0)" id="logoutBtn">退出</a>';
      userBox.querySelector('#logoutBtn').onclick = async () => {
        await API.logout();
        location.reload();
      };
    } else {
      userBox.innerHTML = '<a class="btn primary" href="/login">登录</a>';
    }
  }

  function renderItem(v) {
    const item = document.createElement('section');
    item.className = 'item';
    item.innerHTML =
      '<video src="' + v.url + '" loop playsinline muted preload="metadata"></video>' +
      '<button class="mute-btn" title="静音切换">🔇</button>' +
      '<div class="info">' +
        '<div class="chips">' +
          '<span class="chip cat">' + esc(v.category) + '</span>' +
          (v.reason ? '<span class="chip reason">' + esc(v.reason) + '</span>' : '') +
        '</div>' +
        '<h2>@' + esc(v.uploader) + ' · ' + esc(v.title) + '</h2>' +
        '<div class="tags">' + v.tags.map(t => '#' + esc(t)).join(' ') + '</div>' +
      '</div>' +
      '<div class="rail">' +
        '<button class="like" data-vid="' + v.id + '">' +
          '<span class="icon">❤</span><span class="cnt">' + v.likes + '</span>' +
        '</button>' +
        '<div class="views">▶<br>' + v.views + '</div>' +
      '</div>';

    const video = item.querySelector('video');
    const muteBtn = item.querySelector('.mute-btn');
    let sentView = false;
    let lastProgressAt = 0;
    let liked = false;

    // 静音切换
    muteBtn.onclick = () => {
      video.muted = !video.muted;
      muteBtn.textContent = video.muted ? '🔇' : '🔊';
      if (!video.muted) video.play().catch(() => {});
    };

    // 播放埋点：首次播放记 view，5 秒心跳记 progress，播完记 finish
    video.addEventListener('playing', () => {
      if (!sentView) {
        sentView = true;
        API.behavior(v.id, 'view', 0);
      }
    });
    video.addEventListener('timeupdate', () => {
      const now = Date.now();
      const ratio = video.duration ? video.currentTime / video.duration : 0;
      if (now - lastProgressAt > 5000) {
        lastProgressAt = now;
        API.behavior(v.id, 'progress', ratio);
      }
    });
    video.addEventListener('ended', () => {
      API.behavior(v.id, 'finish', 1);
    });

    // 点赞
    const likeBtn = item.querySelector('.like');
    likeBtn.onclick = () => {
      if (!me) { location.href = '/login'; return; }
      liked = !liked;
      likeBtn.classList.toggle('on', liked);
      likeBtn.querySelector('.cnt').textContent = v.likes + (liked ? 1 : 0);
      API.behavior(v.id, liked ? 'like' : 'unlike', 0);
    };

    return item;
  }

  // 滚动到哪个视频就播放哪个，其余暂停
  function setupObserver() {
    const videos = feed.querySelectorAll('video');
    const io = new IntersectionObserver((entries) => {
      entries.forEach(en => {
        const vd = en.target;
        if (en.isIntersecting && en.intersectionRatio > 0.6) {
          vd.play().catch(() => {});
        } else {
          vd.pause();
        }
      });
    }, { threshold: [0, 0.6, 1] });
    videos.forEach(v => io.observe(v));
  }

  async function loadFeed() {
    feed.innerHTML = '<div class="loading"><div class="spin"></div>正在为你准备视频…</div>';
    try {
      const data = await API.get('/api/feed?count=12');
      feed.innerHTML = '';
      if (!data.items.length) {
        feed.innerHTML =
          '<div class="empty"><div class="spin"></div>' +
          '还没有视频，先运行 <b>python seed.py</b> 初始化演示数据，' +
          '或<a href="/upload">上传第一个视频</a></div>';
        return;
      }
      data.items.forEach(v => feed.appendChild(renderItem(v)));
      setupObserver();
    } catch (e) {
      feed.innerHTML =
        '<div class="empty"><div class="spin"></div>加载失败：' + esc(e.message) + '</div>';
    }
  }

  refreshBtn.onclick = () => {
    loadFeed();
    feed.scrollTo({ top: 0, behavior: 'smooth' });
  };

  (async function init() {
    me = await API.me();
    renderUserBox();
    loadFeed();
  })();
})();
