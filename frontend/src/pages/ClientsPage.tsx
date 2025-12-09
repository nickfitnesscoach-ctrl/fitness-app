import React from 'react';
import { Search, UserPlus, ArrowLeft, User } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useClientsList } from '../hooks/useClientsList';
import { ClientDetails } from '../components/clients/ClientDetails';
import { ClientCard } from '../components/clients/ClientCard';

const ClientsPage: React.FC = () => {
    const navigate = useNavigate();
    const {
        searchTerm,
        setSearchTerm,
        selectedClient,
        setSelectedClient,
        filteredClients,
        handleRemoveClient,
        handleOpenChat,
    } = useClientsList();

    if (selectedClient) {
        return (
            <ClientDetails
                client={selectedClient}
                onBack={() => setSelectedClient(null)}
                onOpenChat={handleOpenChat}
                onRemoveClient={handleRemoveClient}
            />
        );
    }

    return (
        <div className="space-y-6 pb-20">
            <div className="flex items-center justify-between">
                <button onClick={() => navigate('/panel')} className="p-2 -ml-2 text-gray-600">
                    <ArrowLeft size={24} />
                </button>
                <h1 className="text-xl font-bold">Мои клиенты</h1>
                <div className="w-8"></div>
            </div>

            <button
                onClick={() => navigate('/panel/invite-client')}
                className="w-full bg-blue-500 text-white py-4 rounded-2xl font-bold text-base flex items-center justify-center gap-2 shadow-lg active:scale-98 transition-transform"
            >
                <UserPlus size={22} />
                Пригласить клиента
            </button>

            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
                <input
                    type="text"
                    placeholder="Поиск клиентов..."
                    className="w-full bg-white border border-gray-200 rounded-xl pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-blue-500 transition-colors"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
            </div>

            <div className="space-y-3">
                {filteredClients.map(client => (
                    <ClientCard
                        key={client.id}
                        client={client}
                        onView={() => setSelectedClient(client)}
                        onOpenChat={() => handleOpenChat(client.username)}
                    />
                ))}

                {filteredClients.length === 0 && (
                    <div className="text-center text-gray-500 py-12">
                        <User size={48} className="mx-auto mb-3 opacity-30" />
                        <p className="font-medium">Клиентов не найдено</p>
                        <p className="text-sm mt-1">Добавьте клиентов из заявок</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ClientsPage;
