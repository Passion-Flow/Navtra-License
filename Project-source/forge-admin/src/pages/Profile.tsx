// Self-service account page — every member edits their own name / email / avatar and password.
import { useRef, useState } from "react";
import { api, ApiException } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { Button, TextField } from "@/components/ui";
import { Card, PageHeader } from "@/components/widgets";
import { useI18n } from "@/i18n/useI18n";

// Downscale any picked image to a 256×256 cover JPEG data URI — keeps avatars tiny (well under the
// server's size cap) and uniform, no file storage needed.
function fileToAvatar(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("read"));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("decode"));
      img.onload = () => {
        const S = 256;
        const canvas = document.createElement("canvas");
        canvas.width = S;
        canvas.height = S;
        const ctx = canvas.getContext("2d")!;
        const scale = Math.max(S / img.width, S / img.height);
        const w = img.width * scale;
        const h = img.height * scale;
        ctx.drawImage(img, (S - w) / 2, (S - h) / 2, w, h);
        resolve(canvas.toDataURL("image/jpeg", 0.85));
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  });
}

export default function Profile() {
  const { t, tError } = useI18n();
  const { user, refresh } = useAuth();
  const fileRef = useRef<HTMLInputElement>(null);

  const [username, setUsername] = useState(user?.username ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [avatar, setAvatar] = useState<string | null>(user?.avatar ?? null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileMsg, setProfileMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const [curPw, setCurPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [savingPw, setSavingPw] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function onPickFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    try {
      setAvatar(await fileToAvatar(file));
      setProfileMsg(null);
    } catch {
      setProfileMsg({ ok: false, text: tError("SYSTEM_INTERNAL_ERROR") });
    }
  }

  async function saveProfile() {
    setSavingProfile(true);
    setProfileMsg(null);
    try {
      await api.patch("/me/profile", { username, email, avatar: avatar ?? "" });
      await refresh();
      setProfileMsg({ ok: true, text: t("profile.saved") });
    } catch (err) {
      setProfileMsg({ ok: false, text: err instanceof ApiException ? tError(err.error.code) : tError("SYSTEM_INTERNAL_ERROR") });
    } finally {
      setSavingProfile(false);
    }
  }

  async function changePassword() {
    setPwMsg(null);
    if (newPw !== confirmPw) {
      setPwMsg({ ok: false, text: t("profile.pw_mismatch") });
      return;
    }
    setSavingPw(true);
    try {
      await api.post("/me/password", { current_password: curPw, new_password: newPw });
      setCurPw("");
      setNewPw("");
      setConfirmPw("");
      setPwMsg({ ok: true, text: t("profile.pw_changed") });
    } catch (err) {
      setPwMsg({ ok: false, text: err instanceof ApiException ? tError(err.error.code) : tError("SYSTEM_INTERNAL_ERROR") });
    } finally {
      setSavingPw(false);
    }
  }

  const initial = (username || "?").charAt(0).toUpperCase();
  const roleLabel = user?.role ? t(`users.role_${user.role}`) : "";

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-2xl pb-6">
        <PageHeader title={t("profile.title")} subtitle={t("profile.subtitle")} />

      <Card className="p-6">
        {/* identity header */}
        <div className="flex items-center gap-4">
          {avatar ? (
            <img src={avatar} alt={username} className="h-16 w-16 rounded-full object-cover ring-2 ring-zinc-100 dark:ring-zinc-800" />
          ) : (
            <span className="flex h-16 w-16 items-center justify-center rounded-full bg-zinc-900 text-2xl font-semibold text-white dark:bg-white dark:text-zinc-900">
              {initial}
            </span>
          )}
          <div className="min-w-0 flex-1">
            <div className="truncate text-base font-semibold text-zinc-900 dark:text-zinc-100">{username || "—"}</div>
            <span className="mt-1 inline-flex rounded-full bg-brand/10 px-2.5 py-0.5 text-xs font-medium text-brand">{roleLabel}</span>
          </div>
          <div className="flex shrink-0 gap-2">
            <Button type="button" variant="ghost" onClick={() => fileRef.current?.click()}>{t("profile.upload_avatar")}</Button>
            {avatar && <Button type="button" variant="ghost" onClick={() => setAvatar(null)}>{t("profile.remove_avatar")}</Button>}
            <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onPickFile} />
          </div>
        </div>

        <div className="my-5 border-t border-zinc-200 dark:border-zinc-800" />

        <div className="space-y-4">
          <TextField label={t("profile.username")} value={username} onChange={(e) => setUsername(e.target.value)} />
          <TextField label={t("profile.email")} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>

        <div className="mt-5 flex items-center gap-3">
          <Button onClick={saveProfile} disabled={savingProfile}>{t("profile.save")}</Button>
          {profileMsg && <span className={`text-sm ${profileMsg.ok ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>{profileMsg.text}</span>}
        </div>
      </Card>

      <Card className="mt-5 p-6">
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{t("profile.change_password")}</h3>
        <div className="mt-4 space-y-4">
          <TextField label={t("profile.current_password")} type="password" value={curPw} onChange={(e) => setCurPw(e.target.value)} />
          <TextField label={t("profile.new_password")} type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} minLength={8} />
          <TextField label={t("profile.confirm_password")} type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} minLength={8} />
        </div>

        <div className="mt-5 flex items-center gap-3">
          <Button onClick={changePassword} disabled={savingPw}>{t("profile.change_password")}</Button>
          {pwMsg && <span className={`text-sm ${pwMsg.ok ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}>{pwMsg.text}</span>}
        </div>
      </Card>
      </div>
    </div>
  );
}
