import React from 'react';

interface CalendarProps {
    selectedDate: Date;
    onDateSelect: (date: Date) => void;
}

const Calendar: React.FC<CalendarProps> = ({ selectedDate, onDateSelect }) => {
    const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

    // Generate week days array
    const getWeekDays = () => {
        const days = [];
        const today = new Date();
        const currentDay = today.getDay();
        const monday = new Date(today);
        monday.setDate(today.getDate() - (currentDay === 0 ? 6 : currentDay - 1));

        for (let i = 0; i < 7; i++) {
            const date = new Date(monday);
            date.setDate(monday.getDate() + i);
            days.push(date);
        }
        return days;
    };

    const weekDays = getWeekDays();

    const isSameDate = (date1: Date, date2: Date) => {
        return date1.getDate() === date2.getDate() &&
            date1.getMonth() === date2.getMonth() &&
            date1.getFullYear() === date2.getFullYear();
    };

    const handleTodayClick = () => {
        onDateSelect(new Date());
    };

    return (
        <div className="bg-white rounded-3xl shadow-lg p-4 mb-6">
            <div className="flex justify-between items-center mb-4 px-1">
                <span className="text-gray-500 text-sm font-medium">
                    {selectedDate.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}
                </span>
                <button
                    onClick={handleTodayClick}
                    className="px-3 py-1 bg-blue-50 text-blue-600 rounded-full text-xs font-medium hover:bg-blue-100 transition-colors"
                >
                    Сегодня
                </button>
            </div>
            <div className="grid grid-cols-7 gap-2">
                {weekDays.map((date, index) => {
                    const isToday = isSameDate(date, new Date());
                    const isSelected = isSameDate(date, selectedDate);

                    return (
                        <button
                            key={index}
                            onClick={() => onDateSelect(date)}
                            className={`flex flex-col items-center p-3 rounded-2xl transition-all ${isSelected
                                ? 'bg-gradient-to-br from-blue-500 to-purple-500 text-white shadow-lg scale-105'
                                : isToday
                                    ? 'bg-blue-50 text-blue-600'
                                    : 'hover:bg-gray-50 text-gray-600'
                                }`}
                        >
                            <span className={`text-xs font-medium mb-1 ${isSelected ? 'text-white' : 'text-gray-500'}`}>
                                {dayNames[index]}
                            </span>
                            <span className={`text-lg font-bold ${isSelected ? 'text-white' : ''}`}>
                                {date.getDate()}
                            </span>
                        </button>
                    );
                })}
            </div>
        </div>
    );
};

export default Calendar;
