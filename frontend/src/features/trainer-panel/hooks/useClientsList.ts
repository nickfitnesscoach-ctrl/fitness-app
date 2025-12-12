import { useState, useMemo } from 'react';
import { useClients } from '../../../contexts/ClientsContext';
import { Application } from '../types/application';

export const useClientsList = () => {
    const { clients, removeClient } = useClients();
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedClient, setSelectedClient] = useState<Application | null>(null);

    const filteredClients = useMemo(() => {
        return clients.filter(client =>
            client.first_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            client.username.toLowerCase().includes(searchTerm.toLowerCase())
        );
    }, [clients, searchTerm]);

    const handleRemoveClient = (clientId: number) => {
        const tg = window.Telegram?.WebApp;

        const confirmRemove = () => {
            if (selectedClient && selectedClient.id === clientId) {
                setSelectedClient(null);
            }
            removeClient(clientId);
        };

        if (tg?.showConfirm) {
            tg.showConfirm('Удалить клиента из списка?', (confirmed: boolean) => {
                if (confirmed) confirmRemove();
            });
        } else if (window.confirm('Удалить клиента из списка?')) {
            confirmRemove();
        }
    };

    const handleOpenChat = (username: string) => {
        if (username && username !== 'anon') {
            const tg = window.Telegram?.WebApp;
            if (tg?.openTelegramLink) {
                tg.openTelegramLink(`https://t.me/${username}`);
            } else {
                window.open(`https://t.me/${username}`, '_blank');
            }
        }
    };

    return {
        searchTerm,
        setSearchTerm,
        selectedClient,
        setSelectedClient,
        filteredClients,
        handleRemoveClient,
        handleOpenChat,
    };
};
