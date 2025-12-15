/**
 * Trainer Panel Types - Re-export (SSOT)
 *
 * IMPORT POLICY:
 * - External files (contexts/, services/): import from 'features/trainer-panel/types'
 * - Internal files (within feature): import from '../types'
 *
 * Example:
 *   import type { Application, ApplicationResponse } from 'features/trainer-panel/types';
 */

export type {
    Application,
    ApplicationResponse,
    ApplicationDetails,
    ApplicationStatusApi,
    ApplicationStatusUi,
    ClientDetailsApi,
    ClientDetailsUi,
    BodyTypeInfo,
} from './application';
