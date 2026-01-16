import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Calendar as CalendarIcon } from 'lucide-react';
import { useBodyScrollLock } from '../hooks/useBodyScrollLock';

interface CalendarProps {
    selectedDate: Date;
    onDateSelect: (date: Date) => void;
}

const Calendar: React.FC<CalendarProps> = ({ selectedDate, onDateSelect }) => {
    const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
    const monthNames = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];
    const [currentWeekOffset, setCurrentWeekOffset] = useState(0);
    const [showDatePicker, setShowDatePicker] = useState(false);
    const [pickerYear, setPickerYear] = useState(selectedDate.getFullYear());
    const [pickerMonth, setPickerMonth] = useState(selectedDate.getMonth());

    useBodyScrollLock(showDatePicker);

    // Generate week days array based on selected date and week offset
    const getWeekDays = () => {
        const days = [];
        const baseDate = new Date(selectedDate);
        const currentDay = baseDate.getDay();
        const monday = new Date(baseDate);
        monday.setDate(baseDate.getDate() - (currentDay === 0 ? 6 : currentDay - 1));

        // Apply week offset
        monday.setDate(monday.getDate() + (currentWeekOffset * 7));

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
        setCurrentWeekOffset(0);
    };

    const handlePreviousWeek = () => {
        setCurrentWeekOffset(prev => prev - 1);
    };

    const handleNextWeek = () => {
        setCurrentWeekOffset(prev => prev + 1);
    };

    const handleMonthClick = () => {
        setPickerYear(selectedDate.getFullYear());
        setPickerMonth(selectedDate.getMonth());
        setShowDatePicker(true);
    };

    const handleDatePickerSelect = (year: number, month: number, day: number) => {
        const newDate = new Date(year, month, day);
        onDateSelect(newDate);
        setCurrentWeekOffset(0);
        setShowDatePicker(false);
    };

    const getDaysInMonth = (year: number, month: number) => {
        return new Date(year, month + 1, 0).getDate();
    };

    const getFirstDayOfMonth = (year: number, month: number) => {
        const firstDay = new Date(year, month, 1).getDay();
        return firstDay === 0 ? 6 : firstDay - 1; // Convert to Monday-based (0 = Monday)
    };

    // Get month and year from first day of current week
    const firstDayOfWeek = weekDays[0];
    const monthYearText = firstDayOfWeek.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' });

    return (
        <div className="bg-white rounded-3xl shadow-lg p-4 mb-6">
            <div className="flex justify-between items-center mb-4 px-1">
                <div className="flex items-center gap-2">
                    <button
                        onClick={handlePreviousWeek}
                        className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                        aria-label="Предыдущая неделя"
                    >
                        <ChevronLeft size={20} className="text-gray-600" />
                    </button>
                    <button
                        onClick={handleMonthClick}
                        className="flex items-center gap-1 px-2 py-1 hover:bg-gray-100 rounded-lg transition-colors"
                    >
                        <CalendarIcon size={16} className="text-gray-500" />
                        <span className="text-gray-500 text-sm font-medium">
                            {monthYearText}
                        </span>
                    </button>
                    <button
                        onClick={handleNextWeek}
                        className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors"
                        aria-label="Следующая неделя"
                    >
                        <ChevronRight size={20} className="text-gray-600" />
                    </button>
                </div>
                <button
                    onClick={handleTodayClick}
                    className="px-3 py-1 bg-blue-50 text-blue-600 rounded-full text-xs font-medium hover:bg-blue-100 transition-colors"
                >
                    Сегодня
                </button>
            </div>
            <div className="grid grid-cols-7 gap-1 sm:gap-2">
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

            {/* Date Picker Modal */}
            {showDatePicker && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => setShowDatePicker(false)}>
                    <div className="bg-white rounded-3xl p-6 max-w-sm w-full shadow-2xl" onClick={(e) => e.stopPropagation()}>
                        {/* Month and Year Selection */}
                        <div className="flex items-center justify-between mb-6">
                            <button
                                onClick={() => setPickerMonth(prev => prev === 0 ? 11 : prev - 1)}
                                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                            >
                                <ChevronLeft size={20} />
                            </button>
                            <div className="flex flex-col items-center">
                                <select
                                    value={pickerMonth}
                                    onChange={(e) => setPickerMonth(parseInt(e.target.value))}
                                    className="text-lg font-bold text-gray-900 bg-transparent border-none cursor-pointer hover:bg-gray-50 rounded px-2 py-1"
                                >
                                    {monthNames.map((month, index) => (
                                        <option key={index} value={index}>{month}</option>
                                    ))}
                                </select>
                                <select
                                    value={pickerYear}
                                    onChange={(e) => setPickerYear(parseInt(e.target.value))}
                                    className="text-sm text-gray-600 bg-transparent border-none cursor-pointer hover:bg-gray-50 rounded px-2"
                                >
                                    {Array.from({ length: 10 }, (_, i) => new Date().getFullYear() - 5 + i).map(year => (
                                        <option key={year} value={year}>{year}</option>
                                    ))}
                                </select>
                            </div>
                            <button
                                onClick={() => setPickerMonth(prev => prev === 11 ? 0 : prev + 1)}
                                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                            >
                                <ChevronRight size={20} />
                            </button>
                        </div>

                        {/* Calendar Grid */}
                        <div className="grid grid-cols-7 gap-1 mb-4">
                            {dayNames.map(day => (
                                <div key={day} className="text-center text-xs font-medium text-gray-500 py-2">
                                    {day}
                                </div>
                            ))}
                            {Array.from({ length: getFirstDayOfMonth(pickerYear, pickerMonth) }).map((_, i) => (
                                <div key={`empty-${i}`} />
                            ))}
                            {Array.from({ length: getDaysInMonth(pickerYear, pickerMonth) }).map((_, i) => {
                                const day = i + 1;
                                const date = new Date(pickerYear, pickerMonth, day);
                                const isToday = isSameDate(date, new Date());
                                const isSelected = isSameDate(date, selectedDate);

                                return (
                                    <button
                                        key={day}
                                        onClick={() => handleDatePickerSelect(pickerYear, pickerMonth, day)}
                                        className={`p-2 rounded-lg text-sm font-medium transition-colors ${isSelected
                                                ? 'bg-gradient-to-br from-blue-500 to-purple-500 text-white'
                                                : isToday
                                                    ? 'bg-blue-50 text-blue-600'
                                                    : 'hover:bg-gray-100 text-gray-700'
                                            }`}
                                    >
                                        {day}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Close Button */}
                        <button
                            onClick={() => setShowDatePicker(false)}
                            className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-medium transition-colors"
                        >
                            Закрыть
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Calendar;
