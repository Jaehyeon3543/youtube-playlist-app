let player;
let currentIndex = 0;

const items = Array.from(document.querySelectorAll(".playlist-item"));

function setActive(index) {
  items.forEach((item, i) => item.classList.toggle("active", i === index));
}

function playIndex(index) {
  if (!player || items.length === 0) return;
  currentIndex = (index + items.length) % items.length;
  player.loadVideoById(items[currentIndex].dataset.videoId);
  setActive(currentIndex);
}

function onPlayerStateChange(event) {
  if (event.data === YT.PlayerState.ENDED) {
    playIndex(currentIndex + 1);
  }
}

function onYouTubeIframeAPIReady() {
  if (items.length === 0) return;
  player = new YT.Player("yt-player", {
    width: "100%",
    height: "100%",
    videoId: items[0].dataset.videoId,
    playerVars: { rel: 0 },
    events: {
      onReady: () => setActive(0),
      onStateChange: onPlayerStateChange,
    },
  });
}

items.forEach((item, index) => {
  item.addEventListener("click", (event) => {
    if (event.target.closest(".item-actions")) return;
    playIndex(index);
  });
});
