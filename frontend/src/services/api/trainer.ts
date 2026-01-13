/**
 * Trainer Panel API Module
 *
 * SSOT for all Trainer Panel API calls.
 * Endpoints:
 * - Applications
 * - Clients
 * - Invite links
 * - Subscribers
 *
 * IMPORT POLICY (canon):
 *   import { api } from 'services/api';
 *   await api.getApplications();
 *
 * DO NOT import trainer functions from auth.ts (deprecated).
 *
 * @module services/api/trainer
 */

import { fetchWithTimeout, getHeaders, log } from './client';
import { URLS } from './urls';
import { TELEGRAM_BOT_NAME } from '../../config/env';
import type { ApplicationResponse, ApplicationStatusApi, ClientDetailsApi } from '../../features/trainer-panel/types';

// ============================================================
// API Types (non-feature specific)
// ============================================================

export interface Client {
    id: number;
    telegram_id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    photo_url?: string;
    created_at: string;
    details: ClientDetailsApi;
}

export interface Subscriber {
    id: number;
    telegram_id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    plan_type: 'free' | 'monthly' | 'yearly';
    subscribed_at?: string;
    expires_at?: string;
    is_active: boolean;
}

export interface SubscribersStats {
    total: number;
    free: number;
    monthly: number;
    yearly: number;
    revenue: number;
}

export interface SubscribersResponse {
    subscribers: Subscriber[];
    stats: SubscribersStats;
}

export interface InviteLinkResponse {
    link: string;
}

export type ClientsResponse = Client[];
export type ApplicationsResponse = ApplicationResponse[];

// ============================================================
// Applications API
// ============================================================

export const getApplications = async (): Promise<ApplicationsResponse> => {
    try {
        log('Fetching applications');
        const response = await fetchWithTimeout(URLS.applications, {
            headers: getHeaders(),
        });

        if (!response.ok) throw new Error('Failed to fetch applications');
        return (await response.json()) as ApplicationsResponse;
    } catch (error) {
        console.error('Error fetching applications:', error);
        return [];
    }
};

export const deleteApplication = async (applicationId: number): Promise<boolean> => {
    try {
        log(`Deleting application ${applicationId}`);
        const response = await fetchWithTimeout(`${URLS.applications}${applicationId}/`, {
            method: 'DELETE',
            headers: getHeaders(),
        });

        if (!response.ok) throw new Error('Failed to delete application');
        return true;
    } catch (error) {
        console.error('Error deleting application:', error);
        throw error;
    }
};

export const updateApplicationStatus = async (
    applicationId: number,
    status: ApplicationStatusApi
): Promise<ApplicationResponse> => {
    try {
        log(`Updating application ${applicationId} status to ${status}`);
        const response = await fetchWithTimeout(`${URLS.applications}${applicationId}/status/`, {
            method: 'PATCH',
            headers: getHeaders(),
            body: JSON.stringify({ status }),
        });

        if (!response.ok) throw new Error('Failed to update status');
        return (await response.json()) as ApplicationResponse;
    } catch (error) {
        console.error('Error updating status:', error);
        throw error;
    }
};

// ============================================================
// Clients API
// ============================================================

export const getClients = async (): Promise<ClientsResponse> => {
    try {
        log('Fetching clients');
        const response = await fetchWithTimeout(
            URLS.clients,
            { headers: getHeaders() },
            undefined,
            true // skipAuthCheck to avoid global redirects for admin check
        );

        if (response.status === 403) {
            log('User is not an admin, returning empty clients list');
            return [];
        }

        if (!response.ok) throw new Error('Failed to fetch clients');
        return (await response.json()) as ClientsResponse;
    } catch (error) {
        console.error('Error fetching clients:', error);
        return [];
    }
};

export const addClient = async (clientId: number): Promise<Client> => {
    try {
        log(`Adding client ${clientId}`);
        const response = await fetchWithTimeout(`${URLS.clients}${clientId}/add/`, {
            method: 'POST',
            headers: getHeaders(),
        });

        if (!response.ok) throw new Error('Failed to add client');
        return (await response.json()) as Client;
    } catch (error) {
        console.error('Error adding client:', error);
        throw error;
    }
};

export const removeClient = async (clientId: number): Promise<boolean> => {
    try {
        log(`Removing client ${clientId}`);
        const response = await fetchWithTimeout(`${URLS.clients}${clientId}/`, {
            method: 'DELETE',
            headers: getHeaders(),
        });

        if (!response.ok) throw new Error('Failed to remove client');
        return true;
    } catch (error) {
        console.error('Error removing client:', error);
        throw error;
    }
};

// ============================================================
// Invite Link API
// ============================================================

export const getInviteLink = async (): Promise<string> => {
    try {
        log('Fetching invite link');
        const response = await fetchWithTimeout(URLS.inviteLink, {
            headers: getHeaders(),
        });

        if (!response.ok) throw new Error('Failed to fetch invite link');

        const data = (await response.json()) as InviteLinkResponse;
        return data.link;
    } catch (error) {
        console.error('Error fetching invite link:', error);
        return `https://t.me/${TELEGRAM_BOT_NAME}?start=default`;
    }
};

// ============================================================
// Subscribers API
// ============================================================

export const getSubscribers = async (): Promise<SubscribersResponse> => {
    try {
        log('Fetching subscribers');
        const response = await fetchWithTimeout(URLS.subscribers, {
            headers: getHeaders(),
        });

        if (!response.ok) throw new Error('Failed to fetch subscribers');
        return (await response.json()) as SubscribersResponse;
    } catch (error) {
        console.error('Error fetching subscribers:', error);
        return {
            subscribers: [],
            stats: { total: 0, free: 0, monthly: 0, yearly: 0, revenue: 0 },
        };
    }
};
