import { requestJson } from './client';
import { NutritionTargets } from '../types/profile';

export const getTargets = async (): Promise<NutritionTargets> => {
    return requestJson<NutritionTargets>('/nutrition/targets');
};

export const recalculateTargets = async (formula: 'mifflin'): Promise<NutritionTargets> => {
    return requestJson<NutritionTargets>('/nutrition/targets/recalculate', {
        method: 'POST',
        json: { formula },
    });
};
