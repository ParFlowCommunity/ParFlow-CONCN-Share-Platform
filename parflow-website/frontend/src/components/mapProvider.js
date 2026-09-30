import { leafletFallback } from './mapFallback';
import { createSdkLoader } from './mapSdkLoader';

export const mapKey = import.meta.env.VITE_TIANDITU_KEY || '';
const loadConfiguredProvider = createSdkLoader({ document, window, key: mapKey });

export function loadMapProvider() {
  // Preserve the existing unconfigured mode; configured provider errors surface.
  if (!mapKey) return Promise.resolve(leafletFallback());
  return loadConfiguredProvider();
}
