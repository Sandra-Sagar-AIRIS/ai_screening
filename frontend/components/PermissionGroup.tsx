"use client";

import type { PermissionModuleGroup } from "@/lib/api";
import { PermissionCheckbox } from "@/components/PermissionCheckbox";

type PermissionGroupProps = {
  groups: PermissionModuleGroup[];
  selectedPermissions: string[];
  onTogglePermission: (code: string, checked: boolean) => void;
  disabled?: boolean;
};

function formatModuleLabel(module: string) {
  return module.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function PermissionGroup({ groups, selectedPermissions, onTogglePermission, disabled = false }: PermissionGroupProps) {
  return (
    <div className="space-y-4">
      {groups.map((group) => (
        <div key={group.module} className="rounded-md border border-slate-200 p-3">
          <h3 className="mb-2 text-sm font-semibold text-slate-900">{formatModuleLabel(group.module)}</h3>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {group.permissions.map((permission) => (
              <PermissionCheckbox
                key={permission.code}
                permission={permission}
                checked={selectedPermissions.includes(permission.code)}
                onToggle={onTogglePermission}
                disabled={disabled}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
