import { requestJson } from './client';
import { Profile } from '../types/profile';

export const getProfile = async (): Promise<Profile> => {
    return requestJson<Profile>('/profile/me');
};

export const updateProfile = async (payload: Partial<Profile>): Promise<Profile> => {
    return requestJson<Profile>('/profile/me', {
        method: 'PATCH',
        json: payload,
    });
};
