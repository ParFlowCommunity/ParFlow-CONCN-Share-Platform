// A slow first request must not permanently select a different map provider.
export function createSdkLoader({ document, window, key }) {
  let pending;
  return function load() {
    if (window.T?.Map) return Promise.resolve(window.T);
    if (pending) return pending;
    pending = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      const fail = message => {
        script.remove();
        reject(new Error(message));
      };
      script.async = true;
      script.src = `https://api.tianditu.gov.cn/api?v=4.0&tk=${encodeURIComponent(key)}`;
      script.onload = () => {
        if (window.T?.Map) resolve(window.T);
        else fail('天地图脚本已返回，但地图组件不可用。请检查网络后重试。');
      };
      script.onerror = () => fail('天地图加载失败，请检查网络连接后重试。');
      document.head.appendChild(script);
    }).catch(error => {
      pending = undefined;
      throw error;
    });
    return pending;
  };
}
