import { useState } from 'react';
import { User } from 'lucide-react';

interface AvatarProps {
  src?: string;
  alt: string;
  className?: string;
}

/**
 * Avatar component with automatic fallback to default icon
 * Handles broken image URLs gracefully
 */
export function Avatar({ src, alt, className = '' }: AvatarProps) {
  const [imageError, setImageError] = useState(false);

  // Show placeholder if no src or image failed to load
  if (!src || imageError) {
    return (
      <div
        className={`flex items-center justify-center bg-gray-200 ${className}`}
        title={alt}
      >
        <User className="w-1/2 h-1/2 text-gray-400" />
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      onError={() => setImageError(true)}
    />
  );
}
