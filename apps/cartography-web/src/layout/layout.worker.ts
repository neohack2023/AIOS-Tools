/// <reference lib="webworker" />

import { compileLayout } from './strategies';
import type { LayoutRequest } from '../types';

self.onmessage = (event: MessageEvent<LayoutRequest>) => {
  try {
    const result = compileLayout(event.data);
    self.postMessage({ ok: true, result });
  } catch (error) {
    self.postMessage({
      ok: false,
      request_id: event.data.request_id,
      error: error instanceof Error ? error.message : 'Unknown layout error',
    });
  }
};

export {};
