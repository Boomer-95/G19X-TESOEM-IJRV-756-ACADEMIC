--
-- PostgreSQL database dump
--

\restrict zlMtCIHWsM7RF3HAjRrrwYhWZEkHA9JBryfJkhfUefsVSeZCGeSKCqe6zVFxMWX

-- Dumped from database version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: administradores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.administradores (
    id integer NOT NULL,
    username character varying NOT NULL,
    hashed_password character varying NOT NULL,
    nombre_completo character varying,
    activo boolean
);


--
-- Name: administradores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.administradores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: administradores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.administradores_id_seq OWNED BY public.administradores.id;


--
-- Name: clientes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.clientes (
    id integer NOT NULL,
    nombre character varying,
    email character varying,
    telefono character varying,
    score_riesgo double precision,
    probabilidad_pago_a_tiempo double precision,
    segmento character varying
);


--
-- Name: clientes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.clientes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: clientes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.clientes_id_seq OWNED BY public.clientes.id;


--
-- Name: comunicaciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.comunicaciones (
    id integer NOT NULL,
    cliente_id integer,
    estrategia_id integer,
    canal character varying,
    fecha_envio date,
    mensaje character varying,
    exitoso boolean,
    modo character varying(16),
    estado character varying(16),
    provider character varying(16),
    external_id character varying(255),
    error_tecnico character varying(64),
    provider_status character varying(16)
);


--
-- Name: comunicaciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.comunicaciones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: comunicaciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.comunicaciones_id_seq OWNED BY public.comunicaciones.id;


--
-- Name: deudas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.deudas (
    id integer NOT NULL,
    cliente_id integer,
    monto_total double precision,
    saldo_pendiente double precision,
    fecha_vencimiento date,
    estatus character varying,
    probabilidad_pago double precision
);


--
-- Name: deudas_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.deudas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: deudas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.deudas_id_seq OWNED BY public.deudas.id;


--
-- Name: historial_mensajes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.historial_mensajes (
    id integer NOT NULL,
    cliente_id integer,
    contexto_hash character varying(64),
    monto_al_momento double precision,
    mensaje_generado text,
    fecha_creacion timestamp with time zone DEFAULT now()
);


--
-- Name: historial_mensajes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.historial_mensajes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: historial_mensajes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.historial_mensajes_id_seq OWNED BY public.historial_mensajes.id;


--
-- Name: metricas_snapshots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metricas_snapshots (
    id integer NOT NULL,
    fecha date NOT NULL,
    saldo_pendiente numeric(18,2) NOT NULL,
    cartera_vencida numeric(18,2) NOT NULL,
    deudores_activos integer NOT NULL,
    clientes_alto_riesgo integer NOT NULL,
    monto_recuperado numeric(18,2) NOT NULL,
    clientes_con_estrategia_ia integer NOT NULL
);


--
-- Name: metricas_snapshots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metricas_snapshots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metricas_snapshots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metricas_snapshots_id_seq OWNED BY public.metricas_snapshots.id;


--
-- Name: pagos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pagos (
    id integer NOT NULL,
    cliente_id integer,
    deuda_id integer,
    monto double precision NOT NULL,
    fecha_vencimiento date NOT NULL,
    fecha_pago date,
    dias_atraso integer,
    canal_contacto character varying,
    "se_recuperó" boolean
);


--
-- Name: pagos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.pagos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: pagos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.pagos_id_seq OWNED BY public.pagos.id;


--
-- Name: administradores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administradores ALTER COLUMN id SET DEFAULT nextval('public.administradores_id_seq'::regclass);


--
-- Name: clientes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes ALTER COLUMN id SET DEFAULT nextval('public.clientes_id_seq'::regclass);


--
-- Name: comunicaciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comunicaciones ALTER COLUMN id SET DEFAULT nextval('public.comunicaciones_id_seq'::regclass);


--
-- Name: deudas id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deudas ALTER COLUMN id SET DEFAULT nextval('public.deudas_id_seq'::regclass);


--
-- Name: historial_mensajes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_mensajes ALTER COLUMN id SET DEFAULT nextval('public.historial_mensajes_id_seq'::regclass);


--
-- Name: metricas_snapshots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metricas_snapshots ALTER COLUMN id SET DEFAULT nextval('public.metricas_snapshots_id_seq'::regclass);


--
-- Name: pagos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pagos ALTER COLUMN id SET DEFAULT nextval('public.pagos_id_seq'::regclass);


--
-- Data for Name: administradores; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.administradores (id, username, hashed_password, nombre_completo, activo) FROM stdin;
\.


--
-- Data for Name: clientes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.clientes (id, nombre, email, telefono, score_riesgo, probabilidad_pago_a_tiempo, segmento) FROM stdin;
13	Cliente Ficticio Demo 13	cliente13@example.invalid	\N	\N	\N	No definido
14	Cliente Ficticio Demo 14	cliente14@example.invalid	\N	\N	\N	No definido
15	Cliente Ficticio Demo 15	cliente15@example.invalid	\N	\N	\N	Sin deuda
1	Cliente Ficticio Demo 01	cliente01@example.invalid	\N	0.045	0.955	Bajo riesgo
2	Cliente Ficticio Demo 02	cliente02@example.invalid	\N	0.255	0.745	Bajo riesgo
3	Cliente Ficticio Demo 03	cliente03@example.invalid	\N	0.859	0.141	Alto riesgo
4	Cliente Ficticio Demo 04	cliente04@example.invalid	\N	0.321	0.679	Bajo riesgo
5	Cliente Ficticio Demo 05	cliente05@example.invalid	\N	0.481	0.519	Riesgo medio
6	Cliente Ficticio Demo 06	cliente06@example.invalid	\N	0.832	0.168	Alto riesgo
7	Cliente Ficticio Demo 07	cliente07@example.invalid	\N	0.055	0.945	Bajo riesgo
8	Cliente Ficticio Demo 08	cliente08@example.invalid	\N	0.241	0.759	Bajo riesgo
9	Cliente Ficticio Demo 09	cliente09@example.invalid	\N	0.281	0.719	Bajo riesgo
10	Cliente Ficticio Demo 10	cliente10@example.invalid	\N	0.899	0.101	Alto riesgo
11	Cliente Ficticio Demo 11	cliente11@example.invalid	\N	0.286	0.714	Bajo riesgo
12	Cliente Ficticio Demo 12	cliente12@example.invalid	\N	0.9	0.1	Alto riesgo
\.


--
-- Data for Name: comunicaciones; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.comunicaciones (id, cliente_id, estrategia_id, canal, fecha_envio, mensaje, exitoso, modo, estado, provider, external_id, error_tecnico, provider_status) FROM stdin;
1	1	1	Email	2026-09-13	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
2	1	2	SMS	2026-09-11	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
3	2	3	SMS	2026-09-14	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
4	2	4	WhatsApp	2026-09-12	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
5	3	5	WhatsApp	2026-09-15	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
6	3	6	Email	2026-09-13	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
7	4	7	Email	2026-09-16	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
8	4	8	SMS	2026-09-14	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
9	5	9	SMS	2026-09-17	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
10	5	10	WhatsApp	2026-09-15	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
11	6	11	WhatsApp	2026-09-18	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
12	6	12	Email	2026-09-16	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
13	7	13	Email	2026-09-19	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
14	7	14	SMS	2026-09-17	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
15	8	15	SMS	2026-09-20	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
16	8	16	WhatsApp	2026-09-18	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
17	9	17	WhatsApp	2026-09-21	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
18	9	18	Email	2026-09-19	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
19	10	19	Email	2026-09-22	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
20	10	20	SMS	2026-09-20	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
21	11	21	SMS	2026-09-23	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
22	11	22	WhatsApp	2026-09-21	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
23	12	23	WhatsApp	2026-09-24	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
24	12	24	Email	2026-09-22	[DEMO FICTICIA] Recordatorio simulado de revisión de saldo.	f	simulado	Simulado	\N	\N	\N	\N
\.


--
-- Data for Name: deudas; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.deudas (id, cliente_id, monto_total, saldo_pendiente, fecha_vencimiento, estatus, probabilidad_pago) FROM stdin;
13	13	18600	18600	2026-09-03	En Mora	\N
14	14	19800	14850	2027-04-18	Pendiente	\N
15	15	21000	0	2026-09-01	Pagada	\N
16	1	4800	0	2026-08-06	Pagada	\N
17	2	5600	0	2026-08-05	Pagada	\N
18	3	6400	0	2026-08-04	Pagada	\N
19	4	7200	0	2026-08-03	Pagada	\N
20	5	8000	0	2026-08-02	Pagada	\N
21	6	8800	0	2026-08-01	Pagada	\N
22	7	9600	0	2026-07-31	Pagada	\N
23	8	10400	0	2026-07-30	Pagada	\N
1	1	4200	4200	2026-09-15	En Mora	0.955
2	2	5400	4050	2027-04-06	Pendiente	0.745
3	3	6600	6600	2026-09-13	En Mora	0.141
4	4	7800	5850	2026-09-12	En Mora	0.679
5	5	9000	9000	2027-04-09	Pendiente	0.519
6	6	10200	7650	2026-09-10	En Mora	0.168
7	7	11400	11400	2026-09-09	En Mora	0.945
8	8	12600	9450	2027-04-12	Pendiente	0.759
9	9	13800	13800	2026-09-07	En Mora	0.719
10	10	15000	11250	2026-09-06	En Mora	0.101
11	11	16200	16200	2027-04-15	Pendiente	0.714
12	12	17400	13050	2026-09-04	En Mora	0.1
\.


--
-- Data for Name: historial_mensajes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.historial_mensajes (id, cliente_id, contexto_hash, monto_al_momento, mensaje_generado, fecha_creacion) FROM stdin;
1	1	\N	4200	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 01: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-13 06:00:00-06
2	1	\N	4200	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 01: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-11 06:00:00-06
3	2	\N	5400	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 02: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-14 06:00:00-06
4	2	\N	5400	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 02: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-12 06:00:00-06
5	3	\N	6600	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 03: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-15 06:00:00-06
6	3	\N	6600	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 03: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-13 06:00:00-06
7	4	\N	7800	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 04: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-16 06:00:00-06
8	4	\N	7800	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 04: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-14 06:00:00-06
9	5	\N	9000	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 05: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-17 06:00:00-06
10	5	\N	9000	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 05: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-15 06:00:00-06
11	6	\N	10200	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 06: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-18 06:00:00-06
12	6	\N	10200	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 06: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-16 06:00:00-06
13	7	\N	11400	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 07: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-19 06:00:00-06
14	7	\N	11400	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 07: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-17 06:00:00-06
15	8	\N	12600	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 08: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-20 06:00:00-06
16	8	\N	12600	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 08: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-18 06:00:00-06
17	9	\N	13800	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 09: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-21 06:00:00-06
18	9	\N	13800	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 09: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-19 06:00:00-06
19	10	\N	15000	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 10: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-22 06:00:00-06
20	10	\N	15000	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 10: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-20 06:00:00-06
21	11	\N	16200	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 11: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-23 06:00:00-06
22	11	\N	16200	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 11: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-21 06:00:00-06
23	12	\N	17400	[DEMO FICTICIA] Estrategia 1 para Cliente Ficticio Demo 12: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-24 06:00:00-06
24	12	\N	17400	[DEMO FICTICIA] Estrategia 2 para Cliente Ficticio Demo 12: revisar saldo y acordar seguimiento respetuoso. Sin envío externo.	2026-09-22 06:00:00-06
\.


--
-- Data for Name: metricas_snapshots; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.metricas_snapshots (id, fecha, saldo_pendiente, cartera_vencida, deudores_activos, clientes_alto_riesgo, monto_recuperado, clientes_con_estrategia_ia) FROM stdin;
1	2026-09-08	165550.00	103600.00	14	4	60800.00	0
2	2026-09-10	164150.00	102800.00	14	4	60800.00	0
3	2026-09-12	162750.00	102000.00	14	4	60800.00	2
4	2026-09-14	161350.00	101200.00	14	4	60800.00	4
5	2026-09-16	159950.00	100400.00	14	4	60800.00	6
6	2026-09-18	158550.00	99600.00	14	4	60800.00	8
7	2026-09-20	157150.00	98800.00	14	4	86750.00	10
8	2026-09-22	155750.00	98000.00	14	4	91100.00	12
9	2026-09-24	154350.00	97200.00	14	4	94850.00	12
10	2026-09-26	152950.00	96400.00	14	4	98000.00	12
11	2026-09-28	151550.00	95600.00	14	4	100550.00	12
12	2026-09-30	150150.00	94800.00	14	4	102500.00	12
13	2026-10-02	148750.00	94000.00	14	4	103850.00	12
14	2026-10-04	147350.00	93200.00	14	4	103850.00	12
15	2026-10-06	145950.00	92400.00	14	4	103850.00	12
\.


--
-- Data for Name: pagos; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.pagos (id, cliente_id, deuda_id, monto, fecha_vencimiento, fecha_pago, dias_atraso, canal_contacto, "se_recuperó") FROM stdin;
1	2	2	1350	2027-04-06	2026-10-02	-186	Demo sintética	t
2	4	4	1950	2026-09-12	2026-09-30	18	Demo sintética	t
3	6	6	2550	2026-09-10	2026-09-28	18	Demo sintética	t
4	8	8	3150	2027-04-12	2026-09-26	-198	Demo sintética	t
5	10	10	3750	2026-09-06	2026-09-24	18	Demo sintética	t
6	12	12	4350	2026-09-04	2026-09-22	18	Demo sintética	t
7	14	14	4950	2027-04-18	2026-09-20	-210	Demo sintética	t
8	15	15	21000	2026-09-01	2026-09-19	18	Demo sintética	t
9	1	16	1200	2026-08-06	2026-07-25	-12	Demo sintética	t
10	1	16	1200	2026-08-06	2026-07-28	-9	Demo sintética	t
11	1	16	1200	2026-08-06	2026-07-31	-6	Demo sintética	t
12	1	16	1200	2026-08-06	2026-08-03	-3	Demo sintética	t
13	2	17	1400	2026-08-05	2026-08-01	-4	Demo sintética	t
14	2	17	1400	2026-08-05	2026-08-04	-1	Demo sintética	t
15	2	17	1400	2026-08-05	2026-08-07	2	Demo sintética	t
16	2	17	1400	2026-08-05	2026-08-10	5	Demo sintética	t
17	3	18	1600	2026-08-04	2026-08-13	9	Demo sintética	t
18	3	18	1600	2026-08-04	2026-08-16	12	Demo sintética	t
19	3	18	1600	2026-08-04	2026-08-19	15	Demo sintética	t
20	3	18	1600	2026-08-04	2026-08-22	18	Demo sintética	t
21	4	19	1800	2026-08-03	2026-07-22	-12	Demo sintética	t
22	4	19	1800	2026-08-03	2026-07-25	-9	Demo sintética	t
23	4	19	1800	2026-08-03	2026-07-28	-6	Demo sintética	t
24	4	19	1800	2026-08-03	2026-07-31	-3	Demo sintética	t
25	5	20	2000	2026-08-02	2026-07-29	-4	Demo sintética	t
26	5	20	2000	2026-08-02	2026-08-01	-1	Demo sintética	t
27	5	20	2000	2026-08-02	2026-08-04	2	Demo sintética	t
28	5	20	2000	2026-08-02	2026-08-07	5	Demo sintética	t
29	6	21	2200	2026-08-01	2026-08-10	9	Demo sintética	t
30	6	21	2200	2026-08-01	2026-08-13	12	Demo sintética	t
31	6	21	2200	2026-08-01	2026-08-16	15	Demo sintética	t
32	6	21	2200	2026-08-01	2026-08-19	18	Demo sintética	t
33	7	22	2400	2026-07-31	2026-07-19	-12	Demo sintética	t
34	7	22	2400	2026-07-31	2026-07-22	-9	Demo sintética	t
35	7	22	2400	2026-07-31	2026-07-25	-6	Demo sintética	t
36	7	22	2400	2026-07-31	2026-07-28	-3	Demo sintética	t
37	8	23	2600	2026-07-30	2026-07-26	-4	Demo sintética	t
38	8	23	2600	2026-07-30	2026-07-29	-1	Demo sintética	t
39	8	23	2600	2026-07-30	2026-08-01	2	Demo sintética	t
40	8	23	2600	2026-07-30	2026-08-04	5	Demo sintética	t
\.


--
-- Name: administradores_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.administradores_id_seq', 1, false);


--
-- Name: clientes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.clientes_id_seq', 15, true);


--
-- Name: comunicaciones_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.comunicaciones_id_seq', 24, true);


--
-- Name: deudas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.deudas_id_seq', 23, true);


--
-- Name: historial_mensajes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.historial_mensajes_id_seq', 24, true);


--
-- Name: metricas_snapshots_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.metricas_snapshots_id_seq', 15, true);


--
-- Name: pagos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.pagos_id_seq', 40, true);


--
-- Name: administradores administradores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administradores
    ADD CONSTRAINT administradores_pkey PRIMARY KEY (id);


--
-- Name: clientes clientes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_pkey PRIMARY KEY (id);


--
-- Name: comunicaciones comunicaciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comunicaciones
    ADD CONSTRAINT comunicaciones_pkey PRIMARY KEY (id);


--
-- Name: deudas deudas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deudas
    ADD CONSTRAINT deudas_pkey PRIMARY KEY (id);


--
-- Name: historial_mensajes historial_mensajes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_mensajes
    ADD CONSTRAINT historial_mensajes_pkey PRIMARY KEY (id);


--
-- Name: metricas_snapshots metricas_snapshots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metricas_snapshots
    ADD CONSTRAINT metricas_snapshots_pkey PRIMARY KEY (id);


--
-- Name: pagos pagos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pagos
    ADD CONSTRAINT pagos_pkey PRIMARY KEY (id);


--
-- Name: ix_administradores_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_administradores_id ON public.administradores USING btree (id);


--
-- Name: ix_administradores_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_administradores_username ON public.administradores USING btree (username);


--
-- Name: ix_clientes_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_clientes_email ON public.clientes USING btree (email);


--
-- Name: ix_clientes_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clientes_id ON public.clientes USING btree (id);


--
-- Name: ix_clientes_nombre; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_clientes_nombre ON public.clientes USING btree (nombre);


--
-- Name: ix_comunicaciones_estrategia_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comunicaciones_estrategia_id ON public.comunicaciones USING btree (estrategia_id);


--
-- Name: ix_comunicaciones_external_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comunicaciones_external_id ON public.comunicaciones USING btree (external_id);


--
-- Name: ix_comunicaciones_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_comunicaciones_id ON public.comunicaciones USING btree (id);


--
-- Name: ix_deudas_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_deudas_id ON public.deudas USING btree (id);


--
-- Name: ix_historial_mensajes_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_historial_mensajes_id ON public.historial_mensajes USING btree (id);


--
-- Name: ix_metricas_snapshots_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_metricas_snapshots_fecha ON public.metricas_snapshots USING btree (fecha);


--
-- Name: ix_pagos_deuda_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pagos_deuda_id ON public.pagos USING btree (deuda_id);


--
-- Name: ix_pagos_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pagos_id ON public.pagos USING btree (id);


--
-- Name: comunicaciones comunicaciones_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comunicaciones
    ADD CONSTRAINT comunicaciones_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: comunicaciones comunicaciones_estrategia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.comunicaciones
    ADD CONSTRAINT comunicaciones_estrategia_id_fkey FOREIGN KEY (estrategia_id) REFERENCES public.historial_mensajes(id);


--
-- Name: deudas deudas_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.deudas
    ADD CONSTRAINT deudas_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: historial_mensajes historial_mensajes_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_mensajes
    ADD CONSTRAINT historial_mensajes_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: pagos pagos_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pagos
    ADD CONSTRAINT pagos_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: pagos pagos_deuda_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pagos
    ADD CONSTRAINT pagos_deuda_id_fkey FOREIGN KEY (deuda_id) REFERENCES public.deudas(id);


--
-- PostgreSQL database dump complete
--

\unrestrict zlMtCIHWsM7RF3HAjRrrwYhWZEkHA9JBryfJkhfUefsVSeZCGeSKCqe6zVFxMWX
