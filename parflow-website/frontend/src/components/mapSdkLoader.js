// A slow first request must not permanently select a different map provider.
export function createSdkLoader({ document, window, key }) {
  let pending;
  return function load() {
    if (window.T?.Map) return Promise.resolve(window.T);
    if (pending) return pending;
    pending = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      // 错误码供界面按当前语言取文案；本模块不依赖 i18n，保持可独立测试。
      const fail = (message, code) => {
        script.remove();
        reject(Object.assign(new Error(message), { code }));
      };
      script.async = true;
      script.src = `https://api.tianditu.gov.cn/api?v=4.0&tk=${encodeURIComponent(key)}`;
      script.onload = () => {
        if (window.T?.Map) resolve(window.T);
        else fail('天地图脚本已返回，但地图组件不可用。请检查网络后重试。', 'MAP_SDK_UNAVAILABLE');
      };
      script.onerror = () => fail('天地图加载失败，请检查网络连接后重试。', 'MAP_SDK_LOAD_FAILED');
      document.head.appendChild(script);
    }).catch(error => {
      pending = undefined;
      throw error;
    });
    return pending;
  };
}
