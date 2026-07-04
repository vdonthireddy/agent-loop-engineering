import yaml
from dataclasses import dataclass, field
from pathlib import Path

DIRECTIVES = ("extend", "override", "disable", "add")

class LayeredSpecError(Exception):
    pass

@dataclass(slots=True)
class Stack:
    name: str
    language: str = "python"
    backend: str | None = None
    frontend: str | None = None
    database: str | None = None
    tenancy: str | None = None
    test_command: str | None = None
    extra: dict = field(default_factory=dict)

@dataclass(slots=True)
class Feature:
    id: str
    name: str
    body: str

@dataclass(slots=True)
class Override:
    feature: str
    directive: str
    rules: str

@dataclass(slots=True)
class CustomerLayer:
    customer: str
    tenant_id: str
    overrides: list[Override]

@dataclass(slots=True)
class LayeredProject:
    stack: Stack
    features: list[Feature]
    customers: list[CustomerLayer]

    def feature_ids(self) -> set[str]:
        return {f.id for f in self.features}

@dataclass(slots=True)
class ComposedSpec:
    text: str
    title: str
    language: str
    test_command: str | None


def load_project(project_dir: str | Path) -> LayeredProject:
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        raise LayeredSpecError(f"Project directory not found: {project_dir}")
    
    stack = _load_stack(project_dir)
    features = _load_features(project_dir)
    customers = _load_customers(project_dir)
    return LayeredProject(stack=stack, features=features, customers=customers)


def _load_stack(root: Path) -> Stack:
    stack_path = root / "stack.yaml"
    if not stack_path.is_file():
        raise LayeredSpecError(f"stack.yaml not found in {root}")
    
    with open(stack_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise LayeredSpecError("stack.yaml must be a mapping")
        
    known = {"name", "language", "backend", "frontend", "database", "tenancy", "test_command"}
    kwargs = {k: v for k, v in data.items() if k in known}
    extra = {k: v for k, v in data.items() if k not in known}
    if "name" not in kwargs:
        kwargs["name"] = root.name
        
    return Stack(**kwargs, extra=extra)


def _parse_frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("\n---", 1)
        if len(parts) == 2:
            try:
                meta = yaml.safe_load(parts[0][3:]) or {}
                return meta, parts[1].strip()
            except Exception:
                pass
    return {}, text.strip()


def _oneline(text: str) -> str:
    return " ".join(text.split())

def _load_features(root: Path) -> list[Feature]:
    features_dir = root / "features"
    if not features_dir.is_dir():
        raise LayeredSpecError(f"features/ directory not found in {root}")
    
    features = []
    seen = set()
    for f in sorted(features_dir.glob("*.md")):
        meta, body = _parse_frontmatter(f)
        fid = meta.get("id", f.stem)
        name = meta.get("name", f.stem)
        if fid in seen:
            raise LayeredSpecError(f"Duplicate feature id: {fid}")
        seen.add(fid)
        features.append(Feature(id=fid, name=name, body=body))
        
    if not features:
        raise LayeredSpecError("No features found in features/")
    return features


def _load_customers(root: Path) -> list[CustomerLayer]:
    cust_dir = root / "customers"
    if not cust_dir.is_dir():
        return []
    
    customers = []
    for f in sorted(cust_dir.glob("*.y*ml")):
        with open(f, encoding="utf-8") as file:
            data = yaml.safe_load(file)
        if not isinstance(data, dict):
            raise LayeredSpecError(f"Customer file {f} must be a mapping")
            
        customer_name = data.get("customer", f.stem)
        tenant_id = data.get("tenant_id", f.stem)
        overrides = []
        for ov in data.get("overrides", []):
            d = ov.get("directive")
            feat = ov.get("feature")
            rules = ov.get("rules", "").strip()
            if d not in DIRECTIVES:
                raise LayeredSpecError(f"Invalid directive '{d}' in {f}")
            if not feat:
                raise LayeredSpecError(f"Missing feature in override in {f}")
            overrides.append(Override(feature=feat, directive=d, rules=rules))
        customers.append(CustomerLayer(customer=customer_name, tenant_id=tenant_id, overrides=overrides))
    return customers


def _validate(project: LayeredProject):
    fids = project.feature_ids()
    for cust in project.customers:
        for ov in cust.overrides:
            if ov.directive != "add" and ov.feature not in fids:
                raise LayeredSpecError(f"Override for unknown feature: {ov.feature} in {cust.customer}")


def compose(project: LayeredProject) -> ComposedSpec:
    _validate(project)
    
    lines = []
    multi_tenant = bool(project.customers)
    title = project.stack.name
    if multi_tenant:
        title += " — Multi-Tenant Application"
    lines.append(f"# {title}\n")
    
    lines.append("## Tech Stack")
    lines.append(f"- **Language:** {project.stack.language}")
    if project.stack.backend:
        lines.append(f"- **Backend:** {project.stack.backend}")
    if project.stack.frontend:
        lines.append(f"- **Frontend:** {project.stack.frontend}")
    if project.stack.database:
        lines.append(f"- **Database:** {project.stack.database}")
    for k, v in project.stack.extra.items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")
    
    if multi_tenant:
        lines.append("## Tenancy")
        if project.stack.tenancy:
            lines.append(project.stack.tenancy)
        lines.append("Tenants:")
        for cust in project.customers:
            lines.append(f"- {cust.customer} (ID: {cust.tenant_id})")
        lines.append("Tenants:")
        for cust in project.customers:
            lines.append(f"- {cust.customer} (ID: {cust.tenant_id})")
        lines.append("")
        lines.append("Strict data-isolation is required across all tenants.")
        lines.append("")
        
    lines.append("## Global Features")
    for feat in project.features:
        lines.append(f"### {feat.name}")
        lines.append(feat.body)
        
        # Per-tenant variations
        variations = []
        for cust in project.customers:
            for ov in cust.overrides:
                if ov.feature == feat.id and ov.directive != "add":
                    variations.append((cust, ov))
        
        if variations:
            lines.append("\n**Per-tenant variations:**")
            for cust, ov in variations:
                lines.append(f"- **{cust.customer}** (`{cust.tenant_id}`) — _{ov.directive}_: {_oneline(ov.rules)}")
        lines.append("")
        
    # Add directives
    added_features = []
    for cust in project.customers:
        for ov in cust.overrides:
            if ov.directive == "add":
                added_features.append((cust.customer, ov))
                
    if added_features:
        lines.append("## Tenant-specific features")
        for cname, ov in added_features:
            lines.append(f"### {ov.feature} ({cname})")
            lines.append(ov.rules)
            lines.append("")
            
    lines.append("## Cross-cutting requirements")
    lines.append("- A test suite must be written per feature/variation.")
    lines.append("- Per-tenant seed data must be provided.")
    lines.append("- A deploy artifact (e.g. Dockerfile) and DEPLOY.md must be produced.")
    lines.append("- A README.md must be provided explaining what the project is, prerequisites, copy-pasteable install/run commands, and 1-2 example requests.")
    
    return ComposedSpec(
        text="\n".join(lines),
        title=title,
        language=project.stack.language,
        test_command=project.stack.test_command
    )
