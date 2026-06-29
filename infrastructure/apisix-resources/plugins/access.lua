--- 54agent APISIX Access Plugin

local core = require("apisix.core")
local http = require("resty.http")
local jwt = require("resty.jwt")
local ngx = ngx

local plugin_name = "54agent-access-plugin"

local schema = {
    type = "object",
    properties = {
        authorizer_url = {
            type = "string",
            minLength = 1,
            description = "The url used to validate jwt",
        },
        mint_account_url = {
            type = "string",
            minLength = 1,
            description = "The url used to retreive mint account information",
        },
        keycloak_public_key_url = {
            type = "string",
            minLength = 1,
            description = "The url used to retreive tenant keycloak public key",
        },
    },
    required = {"authorizer_url", "mint_account_url", "keycloak_public_key_url"},
}

local _M = {
    version = 0.1,
    priority = 2509,
    name = plugin_name,
    schema = schema,
}

local function fetch_data_from_authorizer(authorizer_url, token, tenant_id, keycloak_realm, keycloak_public_key)
    local httpc = http.new()
    local res, err = httpc:request_uri(authorizer_url .. "/" .. "validate/" .. token, {
        method = "GET",
        headers = {
            ["x-tenant-id"] = tenant_id, -- Add the x-tenant-id header
            ["x-keycloak-realm"] = keycloak_realm, -- Add the x-keycloak-realm header
            ["x-keycloak-pub-key"] = keycloak_public_key, -- Add the x-tenant-id header
        },
    })

    if not res then
        return nil, nil, "failed to verify token: " .. err
    end

    if res.status ~= 200 then
        return nil, nil, "failed to verify token, status: " .. res.status
    end

    local result = core.json.decode(res.body)
    if not result or not result.keycloak_id then
        return nil, nil, "failed to verify token"
    end

    return result.keycloak_id
end

local function fetch_mint_account_data(mint_account_url, tenant_id, ledger_id, keycloak_id)
    local httpc = http.new()
    local res, err = httpc:request_uri(mint_account_url, {
        method = "GET",
        headers = {
            ["x-tenant-id"] = tenant_id, -- Add the x-tenant-id header
            ["x-ledger-id"] = ledger_id, -- Add the x-ledger-id header
            ["x-keycloak-id"] = keycloak_id, -- Add the x-keycloak-id header
        },
    })

    if not res then
        return nil, nil, "failed to get mint account: " .. err
    end

    if res.status ~= 200 then
        return nil, nil, "failed to get mint account, status: " .. res.status
    end

    local result = core.json.decode(res.body)
    if not result or not result.id then
        return nil, nil, "failed to get mint account"
    end

    return result.id
end

local function fetch_tenant_keycloak_public_key(keycloak_public_key_url, tenant_id)
    local httpc = http.new()
    local res, err = httpc:request_uri(keycloak_public_key_url .. "/" .. tenant_id, {
        method = "GET",
        headers = {
            ["x-tenant-id"] = tenant_id, -- Add the x-tenant-id header
        },
    })

    if not res then
        return nil, nil, "failed to get tenant public key: " .. err
    end

    if res.status ~= 200 then
        return nil, nil, "failed to get tenant public key, status: " .. res.status
    end

    local result = core.json.decode(res.body)
    if not result or not result.public_rsa_key then
        return nil, nil, "failed to get tenant public key"
    end
    
    return result.public_rsa_key
end

-- Helper function to extract a cookie by name
local function get_cookie(ctx, cookie_name)
    local cookie_header = ctx.var.http_cookie
    if not cookie_header then
        return nil
    end

    for cookie in string.gmatch(cookie_header, "[^;]+") do
        local key, value = string.match(cookie, "%s*(.-)%s*=%s*(.*)")
        if key == cookie_name then
            return value
        end
    end

    return nil
end

-- Helper function to retrieve token from the request context
local function get_token(ctx)
    -- Try to get the token from query parameter
    local token = core.request.get_uri_args(ctx).token

    -- Fallback to cookies if token is not in query parameter
    if not token then
        token = get_cookie(ctx, "access_token")

        if token then 
            core.log.warn("Token from cookie: " .. token)
        else
            core.log.warn("Token from cookie: null")
        end
    end

     -- Fallback to Authorization header if token is still not found
    if not token then
        local auth_header = core.request.header(ctx, "Authorization")
        if auth_header and auth_header:match("^Bearer%s+(%S+)$") then
            token = auth_header:match("^Bearer%s+(%S+)$")
            core.log.warn("Token from Authorization header: " .. token)
        else
            core.log.warn("Token from Authorization header: null")
        end
    end

    return token
end

function _M.access(conf, ctx)
    local tenant_id = core.request.header(ctx, "x-tenant-id")
    local keycloak_realm = "54agent_" .. tenant_id
    local ledger_id = "1"

    if not tenant_id then
        core.log.warn("Tenant ID not found")
        return 400, {message = "Missing tenant identifier"}
    end

    -- Ignore OPTIONS requests
    if ctx.var.request_method == "OPTIONS" then
        core.log.info("Skipping OPTIONS request")
        return
    end
    
    local token = get_token(ctx)
    if not token then
        core.log.warn("JWT token not found")
        return 401, {message = "Missing JWT token"}
    end

    local keycloak_public_key, err = fetch_tenant_keycloak_public_key(conf.keycloak_public_key_url, tenant_id)
    if not keycloak_public_key then
        return 401, {message = err}
    end

    local keycloak_id, err = fetch_data_from_authorizer(conf.authorizer_url, token, tenant_id, keycloak_realm, keycloak_public_key)
    if not keycloak_id then
        return 401, {message = err}
    end

    local mint_account_id, err = fetch_mint_account_data(conf.mint_account_url, tenant_id, ledger_id, keycloak_id)
    if not mint_account_id then
        return 401, {message = err}
    end

    core.request.set_header(ctx, "x-tenant-id", tenant_id)
    core.request.set_header(ctx, "x-keycloak-id", keycloak_id)
    core.request.set_header(ctx, "x-keycloak-realm", "54agent_" .. tenant_id)
    core.request.set_header(ctx, "x-keycloak-pub-key", keycloak_public_key)
    core.request.set_header(ctx, "x-ledger-id", ledger_id)
    core.request.set_header(ctx, "x-mint-account-id", mint_account_id)
end

function _M.check_schema(conf, schema_type)
    return core.schema.check(schema, conf)
end

return _M
