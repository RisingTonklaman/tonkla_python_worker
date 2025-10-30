CREATE TABLE public.profiles (
    user_id uuid PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
    display_name text NOT NULL,
    avatar_url text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.lists (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.profiles (user_id) ON DELETE CASCADE,
    title text NOT NULL,
    -- ชื่อ list
    color text,
    -- สีธีม เช่น "#ff0000" หรือ "indigo"
    is_archived boolean NOT NULL DEFAULT false,
    position numeric NOT NULL DEFAULT 0,
    -- สำหรับลากเรียง list เอง
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id uuid NOT NULL REFERENCES public.lists (id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.profiles (user_id) ON DELETE CASCADE,
    title text NOT NULL,
    -- หัวข้องาน เช่น "ส่ง report"
    notes text,
    -- รายละเอียด ยาวได้
    status text NOT NULL DEFAULT 'open',
    -- สถานะเสนอ: 'open', 'in_progress', 'done', 'cancelled'
    priority smallint NOT NULL DEFAULT 3,
    -- สมมุติ 1 = สูงสุด 5 = ต่ำสุด
    due_date date,
    -- เส้นตายวันที่
    due_time time,
    -- เส้นตายเวลา (ถ้าอยากเตือนแบบ 17:30)
    is_important boolean NOT NULL DEFAULT false,
    -- ปักดาว
    sort_order numeric NOT NULL DEFAULT 0,
    -- สำหรับ drag & drop ภายใน list
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.tags (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.profiles (user_id) ON DELETE CASCADE,
    name text NOT NULL,
    color text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, name) -- ห้าม tag ชื่อซ้ำในบัญชีเดียวกัน
);
CREATE TABLE public.task_tags (
    task_id uuid NOT NULL REFERENCES public.tasks (id) ON DELETE CASCADE,
    tag_id uuid NOT NULL REFERENCES public.tags (id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, tag_id)
);
CREATE TABLE public.task_activity_log (
    id bigserial PRIMARY KEY,
    task_id uuid NOT NULL REFERENCES public.tasks (id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.profiles (user_id) ON DELETE CASCADE,
    action text NOT NULL,
    -- ตัวอย่างค่า: 'create', 'update_status', 'update_due', 'complete', 'reopen', 'edit_title'
    before_data jsonb,
    after_data jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.reminders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES public.tasks (id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.profiles (user_id) ON DELETE CASCADE,
    remind_at timestamptz NOT NULL,
    -- เวลาแจ้งจริง
    delivered boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.lists (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.profiles (user_id) ON DELETE CASCADE,
    title text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    list_id uuid NOT NULL REFERENCES public.lists (id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES public.profiles (user_id) ON DELETE CASCADE,
    title text NOT NULL,
    notes text,
    status text NOT NULL DEFAULT 'open',
    due_date date,
    due_time time,
    priority smallint NOT NULL DEFAULT 3,
    is_important boolean NOT NULL DEFAULT false,
    sort_order numeric NOT NULL DEFAULT 0,
    completed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);