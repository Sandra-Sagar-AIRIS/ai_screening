"use client";

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";

type PasswordFieldProps = {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  minLength?: number;
};

export function PasswordField({
  id,
  label,
  value,
  onChange,
  placeholder,
  required = true,
  minLength = 8,
}: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);

  return (
    <div className="space-y-2">
      <label className="text-[13px] font-semibold text-gray-700" htmlFor={id}>
        {label}
      </label>
      <div className="relative">
        <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
          <svg className="w-[18px] h-[18px]" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
        </div>
        <Input
          id={id}
          type={visible ? "text" : "password"}
          value={value}
          placeholder={placeholder || "Enter your password"}
          onChange={(event) => onChange(event.target.value)}
          required={required}
          minLength={minLength}
          className="pl-10 pr-10 h-11 bg-white border-gray-200 text-sm focus-visible:ring-1 focus-visible:ring-[#111827] focus-visible:border-[#111827] transition-all rounded-lg"
        />
        <button
          type="button"
          aria-label={visible ? "Hide password" : "Show password"}
          className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-gray-400 hover:text-gray-600 transition-colors"
          onClick={() => setVisible((prev) => !prev)}
        >
          {visible ? <EyeOff size={18} strokeWidth={2} /> : <Eye size={18} strokeWidth={2} />}
        </button>
      </div>
    </div>
  );
}
