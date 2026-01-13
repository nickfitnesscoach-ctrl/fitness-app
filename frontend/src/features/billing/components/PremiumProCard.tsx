// frontend/src/features/billing/components/PremiumProCard.tsx
//
// Карточка тарифа "PRO Год".
// Цель: сохранить дизайн, но сделать вертикальные отступы управляемыми (SSOT).
// Принцип: никаких mb-6/space-y-4 как "рассыпухи" — вместо этого flex-col + gap-*.

import React from 'react';
import { Check, Gift, LineChart, Target } from 'lucide-react';
import { cleanFeatureText } from '../utils/text';

interface PremiumProCardProps {
  displayName: string;
  price: number;
  oldPrice?: number;
  priceSubtext: string;
  features: string[];
  ctaText: string;
  isCurrent: boolean;
  isLoading: boolean;
  disabled?: boolean;
  onSelect: () => void;
  bottomContent?: React.ReactNode;
}

type IconType = 'check' | 'gift' | 'chart' | 'target';

const getIconForFeature = (text: string): IconType => {
  const lower = text.toLowerCase();
  if (lower.includes('стратегия') || lower.includes('бонус')) return 'gift';
  if (lower.includes('аудит') || lower.includes('питания')) return 'chart';
  if (lower.includes('план') || lower.includes('цель')) return 'target';
  return 'check';
};

const getIcon = (iconType: IconType) => {
  switch (iconType) {
    case 'gift':
      return <Gift className="w-4 h-4 text-yellow-400" />;
    case 'chart':
      return <LineChart className="w-4 h-4 text-teal-400" />;
    case 'target':
      return <Target className="w-4 h-4 text-pink-400" />;
    default:
      return <Check className="w-4 h-4 text-emerald-400" />;
  }
};

const getIconBgColor = (iconType: IconType) => {
  switch (iconType) {
    case 'gift':
      return 'bg-yellow-500/20';
    case 'chart':
      return 'bg-teal-500/20';
    case 'target':
      return 'bg-pink-500/20';
    default:
      return 'bg-emerald-500/20';
  }
};

export function PremiumProCard({
  displayName,
  price,
  oldPrice,
  priceSubtext,
  features,
  ctaText,
  isCurrent,
  isLoading,
  disabled,
  onSelect,
  bottomContent,
}: PremiumProCardProps) {
  const isButtonDisabled = Boolean(disabled || isCurrent || isLoading);

  return (
    <div className="relative w-full max-w-md mx-auto">
      {/* ВАЖНО: общий ритм карточки задаём ТОЛЬКО через gap здесь */}
      <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl p-5 sm:p-6 shadow-xl border border-slate-700/50 relative overflow-hidden flex flex-col gap-4">
        {/* Плашка "2 месяца" — без mb, отступ вниз даёт общий gap */}
        <div className="flex justify-end">
          <div className="bg-gradient-to-r from-yellow-400 to-amber-500 text-slate-900 px-3 py-1.5 sm:px-4 sm:py-2 rounded-full text-xs sm:text-sm font-bold flex items-center gap-1.5">
            <Gift className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            2 МЕСЯЦА В ПОДАРОК
          </div>
        </div>

        {/* Хедер: слева тексты, справа цены. Внутри тоже управляем gap, а не mb */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-4">
          <div className="flex flex-col gap-1">
            <p className="text-xs sm:text-sm text-slate-400 uppercase tracking-wide">
              ПРЕМИУМ ФУНКЦИИ
            </p>

            <h2 className="text-2xl sm:text-3xl font-bold text-white">{displayName}</h2>

            <p className="text-xs sm:text-sm text-yellow-400 font-medium">
              ВЫБОР ПОЛЬЗОВАТЕЛЕЙ
            </p>
          </div>

          <div className="flex flex-col gap-1 sm:items-end">
            <div className="flex items-center gap-2 sm:gap-3 justify-end">
              {oldPrice != null ? (
                <span className="text-lg sm:text-xl text-slate-500 line-through">
                  {Math.round(oldPrice)}₽
                </span>
              ) : null}

              <span className="text-3xl sm:text-4xl font-bold text-white">
                {Math.round(price)}₽
              </span>
            </div>

            <span className="text-xs sm:text-sm text-slate-400 text-right uppercase">
              {priceSubtext}
            </span>
          </div>
        </div>

        {/* Фичи: вместо space-y-4 используем flex-col + gap-3 (плотнее и ровнее) */}
        <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-5 border border-slate-700/30">
          <div className="flex flex-col gap-3">
            {features.map((feature, index) => {
              const cleanText = cleanFeatureText(feature);
              const iconType = getIconForFeature(cleanText);

              // Парсим цену в скобках (например: "60-мин стратегия с тренером (5000₽)")
              const priceMatch = cleanText.match(/^(.+?)\s*\((\d+₽)\)$/);
              const displayText = priceMatch ? priceMatch[1] : cleanText;
              const priceInBrackets = priceMatch ? priceMatch[2] : null;

              return (
                <div key={index} className="flex items-center gap-3">
                  <div
                    className={`w-8 h-8 rounded-lg ${getIconBgColor(
                      iconType
                    )} flex items-center justify-center flex-shrink-0`}
                  >
                    {getIcon(iconType)}
                  </div>

                  <span className="text-sm sm:text-base text-slate-200">
                    {displayText}
                    {priceInBrackets && (
                      <>
                        {' '}
                        <span className="text-slate-500 line-through">
                          ({priceInBrackets})
                        </span>
                      </>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Низ: либо кастомный блок, либо кнопка */}
        {bottomContent ? (
          bottomContent
        ) : (
          <button
            type="button"
            onClick={onSelect}
            disabled={isButtonDisabled}
            className={[
              'w-full py-3.5 sm:py-4 bg-gradient-to-r from-yellow-400 to-amber-500 text-slate-900 rounded-2xl font-bold text-sm sm:text-base transition-all uppercase',
              isButtonDisabled
                ? 'opacity-50 cursor-not-allowed filter grayscale'
                : 'hover:from-yellow-300 hover:to-amber-400',
              isLoading ? 'opacity-70 cursor-wait' : '',
            ].join(' ')}
          >
            {isLoading ? (
              <div className="flex items-center justify-center gap-2">
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                <span>Ждем...</span>
              </div>
            ) : (
              ctaText
            )}
          </button>
        )}
      </div>
    </div>
  );
}
