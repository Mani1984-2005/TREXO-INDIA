import { USE_MOCK } from '../config';
import type { TrexoServices } from './interfaces';
import { createApiServices } from './apiServices';
import { createMockServices } from './mockServices';

// VITE_USE_MOCK=false selects the FastAPI backend; the mock remains the
// fallback for offline demos and unit tests.
export const services: TrexoServices = USE_MOCK ? createMockServices() : createApiServices();
