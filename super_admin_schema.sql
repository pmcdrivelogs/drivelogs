-- Super Admins Table Schema
create table public.super_admins (
  id uuid not null default extensions.uuid_generate_v4 (),
  username text not null,
  password text not null,
  full_name text not null,
  email text null,
  phone text null,
  is_active boolean null default true,
  created_at timestamp with time zone null default now(),
  updated_at timestamp with time zone null default now(),
  last_login timestamp with time zone null,
  constraint super_admins_pkey primary key (id),
  constraint super_admins_username_key unique (username)
) TABLESPACE pg_default;

create index IF not exists idx_super_admins_username on public.super_admins using btree (username) TABLESPACE pg_default;

create index IF not exists idx_super_admins_active on public.super_admins using btree (is_active) TABLESPACE pg_default;

create trigger update_super_admins_updated_at BEFORE
update on super_admins for EACH row
execute FUNCTION update_updated_at_column ();
