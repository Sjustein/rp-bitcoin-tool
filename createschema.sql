create sequence "RansomAddressess_Id_seq"
    as integer;

alter sequence "RansomAddressess_Id_seq" owner to rp_admin;

create sequence "StakeholderTransactions_Id_seq";

alter sequence "StakeholderTransactions_Id_seq" owner to rp_admin;

create table "AddressCache"
(
    "Address" varchar(100) not null
        constraint "AddressCache_pk"
            primary key,
    "Content" text,
    "TXCount" integer
);

alter table "AddressCache"
    owner to rp_admin;

create table "BlockCache"
(
    "Blockhash" varchar(255) not null
        constraint "BlockCache_pk"
            primary key,
    "Content"   text         not null
);

alter table "BlockCache"
    owner to rp_admin;

create table "DepositTransactions"
(
    "Id"              bigserial
        constraint "DepositTransactions_pk"
            primary key,
    "VictimAddress"   varchar(255)    not null,
    "Amount"          numeric(30, 25) not null,
    "Time"            integer,
    "TransactionHash" varchar(255)    not null,
    "IsDeposit"       boolean         not null,
    "Address"         varchar(255)    not null,
    "Blockheight"     integer         not null,
    "Blockorder"      integer         not null
);

alter table "DepositTransactions"
    owner to rp_admin;

create index "DepositTransactions_Address_index"
    on "DepositTransactions" ("Address");

create index "DepositTransactions_IsDeposit_index"
    on "DepositTransactions" ("IsDeposit");

create index "DepositTransactions_VictimAddress_IsDeposit_index"
    on "DepositTransactions" ("VictimAddress", "IsDeposit");

create index "DepositTransactions_VictimAddress_index"
    on "DepositTransactions" ("VictimAddress");

create table "VictimAddresses"
(
    "Id"            integer default nextval('"RansomAddressess_Id_seq"'::regclass) not null
        constraint "VictimAddresses_pk"
            primary key,
    "TransactionId" integer                                                        not null,
    "Address"       varchar(100)                                                   not null,
    "Amount"        numeric(30, 25),
    "Failed"        boolean
);

alter table "VictimAddresses"
    owner to rp_admin;

alter sequence "RansomAddressess_Id_seq" owned by "VictimAddresses"."Id";

create table "RansomData"
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
    "Failed"                      boolean default false    not null,
    "FailedVictims"               boolean
);

alter table "RansomData"
    owner to rp_admin;

create unique index "RansomData_Address_uindex"
    on "RansomData" ("Address");

create table "RansomTransactions"
(
    "Id"                  bigserial
        constraint "RansomTransactions_pk"
            primary key,
    "DataId"              integer         not null,
    "Hash"                varchar(100)    not null,
    "Time"                bigint          not null,
    "Amount"              bigint          not null,
    "AmountUSD"           numeric(32, 20) not null,
    "SourceIsHolder"      boolean,
    "DepositPaymentDelta" integer,
    "ConvertedTime"       timestamp       not null
);

alter table "RansomTransactions"
    owner to rp_admin;

create table "StakeholderOutputs"
(
    "Id"                 bigint default nextval('"StakeholderTransactions_Id_seq"'::regclass) not null,
    "AttackerAddress"    varchar(255)                                                         not null,
    "Amount"             numeric(30, 25),
    "Time"               integer,
    "TransactionHash"    varchar(255),
    "StakeholderAddress" varchar(255)                                                         not null,
    "PercentageSplit"    numeric(20, 19),
    "ConvertedTime"      timestamp                                                            not null
);

alter table "StakeholderOutputs"
    owner to rp_admin;

alter sequence "StakeholderTransactions_Id_seq" owned by "StakeholderOutputs"."Id";

create index "StakeholderOutputs_AttackerAddress_index"
    on "StakeholderOutputs" ("AttackerAddress");

create table "TransactionCache"
(
    "TXId"    varchar(100) not null
        constraint "TransactionCache_pk"
            primary key,
    "Content" text
);

alter table "TransactionCache"
    owner to rp_admin;

create table "RaasFamilies"
(
    "Family" varchar(255) not null
        constraint "RaasFamilies_pk"
            primary key,
    "Raas"   boolean      not null
);

alter table "RaasFamilies"
    owner to rp_admin;