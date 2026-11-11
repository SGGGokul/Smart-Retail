import type { CSSProperties, FC } from "react";

export interface MaterialIconProps {
  name: string;
  className?: string;
  size?: number | string;
  filled?: boolean;
  weight?: 100 | 200 | 300 | 400 | 500 | 600 | 700;
  style?: CSSProperties;
  "aria-hidden"?: boolean | "true" | "false";
  "aria-label"?: string;
  title?: string;
}

export const MaterialIcon: FC<MaterialIconProps> = ({
  name,
  className = "",
  size,
  filled = false,
  weight = 400,
  style,
  "aria-hidden": ariaHidden,
  "aria-label": ariaLabel,
  title,
}) => {
  const isAriaHidden = ariaLabel ? false : ariaHidden ?? true;

  const dynamicStyle: CSSProperties = {
    fontVariationSettings: `'FILL' ${filled ? 1 : 0}, 'wght' ${weight}, 'GRAD' 0, 'opsz' 20`,
    ...(size
      ? {
          fontSize: typeof size === "number" ? `${size}px` : size,
          width: typeof size === "number" ? `${size}px` : size,
          height: typeof size === "number" ? `${size}px` : size,
        }
      : {}),
    ...style,
  };

  return (
    <span
      className={`material-symbols-rounded select-none shrink-0 ${className}`}
      style={dynamicStyle}
      aria-hidden={isAriaHidden ? "true" : undefined}
      aria-label={ariaLabel}
      title={title}
    >
      {name}
    </span>
  );
};

export default MaterialIcon;
