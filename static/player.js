let player;
let items = [];
let currentVideoId = null;
let shuffle = false;

const list = document.getElementById("playlist-list");
const shuffleBtn = document.getElementById("shuffle-toggle");

function refreshItems() {
  items = Array.from(document.querySelectorAll(".playlist-item"));
}

function indexOfCurrent() {
  return items.findIndex((item) => item.dataset.videoId === currentVideoId);
}

function setActive() {
  items.forEach((item) => item.classList.toggle("active", item.dataset.videoId === currentVideoId));
}

function playVideoId(videoId) {
  if (!player) return;
  currentVideoId = videoId;
  player.loadVideoById(videoId);
  setActive();
}

function pickNextVideoId() {
  if (items.length === 0) return null;
  if (items.length === 1) return items[0].dataset.videoId;

  if (shuffle) {
    let idx;
    do {
      idx = Math.floor(Math.random() * items.length);
    } while (items[idx].dataset.videoId === currentVideoId);
    return items[idx].dataset.videoId;
  }

  const curIdx = indexOfCurrent();
  const nextIdx = curIdx === -1 ? 0 : (curIdx + 1) % items.length;
  return items[nextIdx].dataset.videoId;
}

function onPlayerStateChange(event) {
  if (event.data === YT.PlayerState.ENDED) {
    const nextId = pickNextVideoId();
    if (nextId) playVideoId(nextId);
  }
}

function onYouTubeIframeAPIReady() {
  refreshItems();
  if (items.length === 0) return;
  currentVideoId = items[0].dataset.videoId;
  player = new YT.Player("yt-player", {
    width: "100%",
    height: "100%",
    videoId: currentVideoId,
    playerVars: { rel: 0 },
    events: {
      onReady: setActive,
      onStateChange: onPlayerStateChange,
    },
  });
}

document.addEventListener("click", (event) => {
  const item = event.target.closest(".playlist-item");
  if (item && !event.target.closest(".item-actions")) {
    playVideoId(item.dataset.videoId);
  }
});

if (shuffleBtn) {
  shuffleBtn.addEventListener("click", () => {
    shuffle = !shuffle;
    shuffleBtn.classList.toggle("active", shuffle);
    shuffleBtn.setAttribute("aria-pressed", String(shuffle));
  });
}

document.querySelectorAll(".star-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const songId = btn.dataset.songId;
    try {
      const res = await fetch(`/song/${songId}/favorite`, { method: "POST" });
      if (!res.ok) return;
      const data = await res.json();
      btn.classList.toggle("active", data.is_favorite);
      btn.textContent = data.is_favorite ? "★" : "☆";
    } catch (err) {
      // 네트워크 오류 시 조용히 무시
    }
  });
});

// 드래그로 순서 바꾸기 (즐겨찾기 통합 화면에서는 장르가 섞여 있어 비활성화됨)
if (list && list.dataset.genre) {
  let dragging = null;

  list.addEventListener("dragstart", (event) => {
    const item = event.target.closest(".playlist-item");
    if (!item) return;
    dragging = item;
    item.classList.add("dragging");
  });

  list.addEventListener("dragend", async () => {
    if (!dragging) return;
    dragging.classList.remove("dragging");
    dragging = null;
    refreshItems();

    const order = Array.from(list.children).map((item) => item.dataset.songId);
    try {
      await fetch(`/genre/${list.dataset.genre}/reorder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order }),
      });
    } catch (err) {
      // 네트워크 오류 시 조용히 무시 - 새로고침하면 원래 저장된 순서로 돌아감
    }
  });

  list.addEventListener("dragover", (event) => {
    event.preventDefault();
    if (!dragging) return;
    const after = Array.from(list.children)
      .filter((item) => item !== dragging)
      .find((item) => event.clientY < item.getBoundingClientRect().top + item.offsetHeight / 2);

    if (after) {
      list.insertBefore(dragging, after);
    } else {
      list.appendChild(dragging);
    }
  });
}
