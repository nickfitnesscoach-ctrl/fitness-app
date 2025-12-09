import React from 'react';

interface InfoItemProps {
    label: string;
    value: string | number;
}

export const InfoItem: React.FC<InfoItemProps> = ({ label, value }) => (
    <div className="bg-gray-50 p-3 rounded-xl flex flex-col">
        <div className="text-xs text-gray-500 mb-1">{label}</div>
        <div className="font-bold text-gray-900 text-right">{value}</div>
    </div>
);
