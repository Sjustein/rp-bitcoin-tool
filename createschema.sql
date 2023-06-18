create sequence "RansomAddressess_Id_seq"
    as integer;

alter sequence "RansomAddressess_Id_seq" owner to rp_admin;

create sequence "StakeholderTransactions_Id_seq";

alter sequence "StakeholderTransactions_Id_seq" owner to rp_admin;

create table if not exists "RansomData"
(
    "Id"                          bigint generated always as identity
        constraint "PK_RansomData"
            primary key,
    "Address"                     varchar(100)             not null,
    "Balance"                     numeric(20)              not null,
    "BlockChain"                  varchar(100)             not null,
    "CreatedAt"                   timestamp with time zone not null,
    "UpdatedAt"                   timestamp with time zone not null,
    "Family"                      varchar(200)             not null,
    "BalanceUSD"                  numeric                  not null,
    "BalanceBTCAfterStakeholders" numeric(30, 25),
    "Failed"                      boolean default false    not null
);

alter table "RansomData"
    owner to rp_admin;

create unique index if not exists "RansomData_Address_uindex"
    on "RansomData" ("Address");

create table if not exists "RansomTransactions"
(
    "Id"        bigserial
        constraint "RansomTransactions_pk"
            primary key,
    "DataId"    integer         not null
        constraint "RansomTransactions_RansomData_Id_fk"
            references "RansomData"
            on update cascade on delete cascade,
    "Hash"      varchar(100)    not null,
    "Time"      bigint          not null,
    "Amount"    bigint          not null,
    "AmountUSD" numeric(32, 20) not null
);

alter table "RansomTransactions"
    owner to rp_admin;

create table if not exists "DepositTransactions"
(
    "Id"              bigserial
        constraint "DepositTransactions_pk"
            primary key,
    "Address"         varchar(255) not null,
    "Amount"          integer      not null,
    "Time"            integer,
    "TransactionHash" varchar(255) not null
);

alter table "DepositTransactions"
    owner to rp_admin;

create table if not exists "TransactionCache"
(
    "TXId"    varchar(100) not null
        constraint "TransactionCache_pk"
            primary key,
    "Content" text
);

alter table "TransactionCache"
    owner to rp_admin;

create table if not exists "AddressCache"
(
    "Address" varchar(100) not null
        constraint "AddressCache_pk"
            primary key,
    "Content" text,
    "TXCount" integer
);

alter table "AddressCache"
    owner to rp_admin;

create table if not exists "VictimAddresses"
(
    "Id"                   integer default nextval('"RansomAddressess_Id_seq"'::regclass) not null
        constraint "VictimAddresses_pk"
            primary key,
    "TransactionId"        integer                                                        not null
        constraint "VictimAddresses_RansomTransactions_Id_fk"
            references "RansomTransactions"
            on update cascade on delete cascade,
    "Address"              varchar(100)                                                   not null,
    "SourceIsHolder"       integer,
    "Amount"               numeric(30, 25),
    "TimeBetweenBuyAndPay" integer
);

alter table "VictimAddresses"
    owner to rp_admin;

alter sequence "RansomAddressess_Id_seq" owned by "VictimAddresses"."Id";

create table if not exists "StakeholderOutputs"
(
    "Id"                 bigint default nextval('"StakeholderTransactions_Id_seq"'::regclass) not null,
    "AttackerAddress"    varchar(255)                                                         not null,
    "Amount"             numeric(30, 25),
    "Time"               integer,
    "TransactionHash"    varchar(255),
    "StakeholderAddress" varchar(255)                                                         not null,
    "PercentageSplit"    numeric(10, 3)
);

alter table "StakeholderOutputs"
    owner to rp_admin;

alter sequence "StakeholderTransactions_Id_seq" owned by "StakeholderOutputs"."Id";

create index if not exists "StakeholderOutputs_AttackerAddress_index"
    on "StakeholderOutputs" ("AttackerAddress");

create table if not exists "InvalidTXIds"
(
    "TXId" varchar(255) not null
        constraint "InvalidTXIds_pk"
            primary key
);

alter table "InvalidTXIds"
    owner to rp_admin;