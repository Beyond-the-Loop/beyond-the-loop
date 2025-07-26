import { WEBUI_API_BASE_URL } from '$lib/constants';


export const getDomains = async (token: string) => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/domains/`, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        },
        credentials: 'include',
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.log(err);
            error = err.detail;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};

export const addDomain = async (token: string, domain: string) => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/domains/create`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        },
        credentials: 'include',
        body: JSON.stringify({
            domain_fqdn: domain
        })
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.log(err);
            error = err.detail;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};

export const switchOwnership = async (token: string, domain_id: string) => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/domains/approve/${domain_id}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        },
        credentials: 'include',
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.log(err);
            error = err.detail;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};

export const deleteDomain = async (token: string, domain_id: string) => {
    let error = null;

    const res = await fetch(`${WEBUI_API_BASE_URL}/domains/delete/${domain_id}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
        },
        credentials: 'include',
    })
        .then(async (res) => {
            if (!res.ok) throw await res.json();
            return res.json();
        })
        .catch((err) => {
            console.log(err);
            error = err.detail;
            return null;
        });

    if (error) {
        throw error;
    }

    return res;
};