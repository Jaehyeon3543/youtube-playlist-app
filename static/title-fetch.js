document.querySelectorAll("form").forEach((form) => {
  const urlInput = form.querySelector(".js-url");
  const titleInput = form.querySelector(".js-title");
  if (!urlInput || !titleInput) return;

  let debounceTimer;
  urlInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      const url = urlInput.value.trim();
      if (!url || titleInput.value.trim()) return;

      try {
        const res = await fetch(`/api/youtube-title?url=${encodeURIComponent(url)}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.title && !titleInput.value.trim()) {
          titleInput.value = data.title;
        }
      } catch (err) {
        // 조회 실패 시 조용히 무시하고 사용자가 직접 입력하도록 둔다
      }
    }, 500);
  });
});
