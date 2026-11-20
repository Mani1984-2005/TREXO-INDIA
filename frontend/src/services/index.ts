import { USE_MOCK } from '../config';
import type { TrexoServices } from './interfaces';
import { createMockServices } from './mockServices';

// Switched via VITE_USE_MOCK so backend REST/GraphQL adapters can be plugged in without changing UI components.
export const services: TrexoServices = USE_MOCK ? createMockServices() : createMockServices();
