"use client";

import type { PermissionItem } from "@/lib/api";

type PermissionCheckboxProps = {
  permission: PermissionItem;
  checked: boolean;
  onToggle: (code: string, checked: boolean) => void;
  disabled?: boolean;
};

export function PermissionCheckbox({ permission, checked, onToggle, disabled = false }: PermissionCheckboxProps) {
  return (
    <label className={`flex items-center gap-2 rounded border border-slate-200 px-3 py-2 text-sm ${disabled ? "opacity-60" : ""}`}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onToggle(permission.code, event.target.checked)}
      />
      <span>{permission.display_name}</span>
    </label>
  );
}
