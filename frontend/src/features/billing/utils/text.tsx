// billing/utils/text.ts
import React from 'react';
import { Zap, Calculator, Calendar, Gift, FileCheck, Target } from 'lucide-react';

/**
 * Remove emoji / replacement chars / zero-width chars.
 * Keeps Cyrillic and useful symbols intact.
 */
export function cleanFeatureText(input: string): string {
    if (!input) return '';

    return input
        .replace(/^\p{Extended_Pictographic}+\s*/u, '') // leading emoji
        .replace(/\uFFFD/g, '') // replacement char
        .replace(/[\u200B-\u200D\uFE0E\uFE0F]/g, '') // zero-width + variation selectors
        .trim();
}

/**
 * Returns a consistent icon by feature semantics (not by emojis).
 */
export function getPlanFeatureIcon(cleanText: string): React.ReactNode | null {
    const t = (cleanText || '').toLowerCase();

    // Bonus / Gift
    if (t.includes('подар') || t.includes('бонус') || t.includes('в подарок')) return <Gift className="w-5 h-5" />;

    // Audit
    if (t.includes('аудит') || t.includes('провер') || t.includes('разбор')) return <FileCheck className="w-5 h-5" />;

    // Goal / Target
    if (t.includes('цель') || t.includes('план') || t.includes('стратег')) return <Target className="w-5 h-5" />;

    // History / Calendar
    if (t.includes('истори') || t.includes('дней') || t.includes('дня') || t.includes('недел')) return <Calendar className="w-5 h-5" />;

    // Calories / KBJU
    if (t.includes('кбжу') || t.includes('калор') || t.includes('расчёт') || t.includes('расчет') || t.includes('подсчет')) {
        return <Calculator className="w-5 h-5" />;
    }

    // AI / limits
    if (t.includes('ai') || t.includes('нейро') || t.includes('распозна') || t.includes('лимит') || t.includes('безлимит')) {
        return <Zap className="w-5 h-5" />;
    }

    return null;
}
