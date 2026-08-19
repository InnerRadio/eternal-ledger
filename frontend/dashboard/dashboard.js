const API_BASE = "/account";

const views = {
    overview: "/dashboard",
    member: "/member",
    creator: "/creator",
    rescue: "/rescue",
    partner: "/partner",
    organization: "/organization",
    leaderboard: "/leaderboard"
};

const titles = {
    overview: "Account Overview",
    member: "Member Dashboard",
    creator: "Creator Dashboard",
    rescue: "Rescue Dashboard",
    partner: "Partner Dashboard",
    organization: "Organization Dashboard",
    leaderboard: "Platform Leaderboard"
};

function setText(id, value){
    const el = document.getElementById(id);
    if(el) el.textContent = value ?? "—";
}

function safeCount(value){
    if(Array.isArray(value)) return value.length;
    if(typeof value === "number") return value;
    return "—";
}

async function fetchJson(path){
    const response = await fetch(API_BASE + path, {
        headers: {"Accept":"application/json"}
    });

    if(!response.ok){
        throw new Error(`${response.status} ${response.statusText}`);
    }

    return response.json();
}

function renderObjectSummary(data){
    const container = document.getElementById("viewContent");
    container.innerHTML = "";

    const keys = [
        "module",
        "status",
        "version",
        "role",
        "account_role",
        "count",
        "total_count"
    ];

    keys.forEach(key => {
        if(data[key] !== undefined){
            const row = document.createElement("div");
            row.className = "data-line";
            row.innerHTML = `<span>${key}</span><strong>${data[key]}</strong>`;
            container.appendChild(row);
        }
    });

    const major = [
        "memorials",
        "contributions",
        "media_assets",
        "campaigns",
        "records",
        "organizations",
        "leaderboard"
    ];

    major.forEach(key => {
        if(data[key] !== undefined){
            const row = document.createElement("div");
            row.className = "data-line";
            row.innerHTML = `<span>${key}</span><strong>${safeCount(data[key])}</strong>`;
            container.appendChild(row);
        }
    });

    if(!container.children.length){
        container.textContent = "Dashboard data loaded.";
    }
}

async function loadPulse(){
    try{
        const data = await fetchJson("/network-pulse");

        const metrics = data.metrics || data.network || data.summary || {};

        setText("metricMembers", metrics.members || metrics.users || data.member_count || "—");
        setText("metricOrganizations", metrics.organizations || data.organization_count || "—");
        setText("metricCampaigns", metrics.active_campaigns || metrics.campaigns || data.active_campaign_count || "—");
        setText("metricMedia", metrics.media_assets || data.media_asset_count || "—");

    }catch(err){
        console.log("Pulse unavailable", err);
    }
}

async function loadCampaigns(){
    try{
        const data = await fetchJson("/partner-campaigns");
        const campaigns = data.records || [];

        const container = document.getElementById("campaignList");
        container.innerHTML = "";

        if(!campaigns.length){
            container.innerHTML = "<p>No partner campaigns yet.</p>";
            return;
        }

        campaigns.slice(0,3).forEach(campaign => {
            const card = document.createElement("div");
            card.className = "campaign-card";
            card.innerHTML = `
                <strong>${campaign.name || "Campaign"}</strong>
                <p>${campaign.partner_organization_name || campaign.status || ""}</p>
            `;
            container.appendChild(card);
        });

    }catch(err){
        console.log("Campaigns unavailable", err);
    }
}

async function loadView(view){
    document.querySelectorAll(".selector").forEach(button => {
        button.classList.toggle("active", button.dataset.view === view);
    });

    setText("viewTitle", titles[view]);
    setText("selectedViewHeading", titles[view]);

    const container = document.getElementById("viewContent");
    container.textContent = "Loading...";

    try{
        const data = await fetchJson(views[view]);
        renderObjectSummary(data);

        if(data.viewer && data.viewer.user_id){
            setText("accountName", `User #${data.viewer.user_id}`);
        }else if(data.user && data.user.email){
            setText("accountName", data.user.email);
        }

    }catch(err){
        container.innerHTML = `
            <div class="data-line"><span>Status</span><strong>Login required</strong></div>
            <p>This dashboard shell is ready. Authenticate to load live account data.</p>
        `;
        console.log("View unavailable", err);
    }
}

document.querySelectorAll(".selector").forEach(button => {
    button.addEventListener("click", () => loadView(button.dataset.view));
});

loadPulse();
loadCampaigns();
loadView("overview");
