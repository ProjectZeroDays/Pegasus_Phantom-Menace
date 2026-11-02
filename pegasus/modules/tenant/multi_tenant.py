"""
Multi-Tenant Architecture for Enterprise Deployments
Enterprise-grade tenant management system for multi-tenant deployments
Supports tenant isolation, resource allocation, security enforcement, and compliance
"""

from typing import *
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing_extensions import TypedDict, ParamSpec
import asyncio
import logging
from uuid import uuid

logger = logging.getLogger(__name__)

class Tenant(BaseModel):
    """Tenant model for multi-tenant architecture"""
    tenant_id: str
    name: str
    domain: str
    tier: str = "standard"
    resources: Dict[str, Any]
    limits: Dict[str, int]
    quotas: Dict[str, float]
    compliance_level: str = "basic"
    security_policy: Dict[str, Any]
    settings: Dict[str, Any] = {}
    is_active: bool = True
    created_at: datetime
    last_seen: datetime

class ResourcePool(BaseModel):
    """Resource pool model for tenant resource management"""
    pool_id: str
    tenant_id: str
    resource_type: str
    total_capacity: float
    allocated_capacity: float = 0.0
    available_capacity: float = 0.0
    unit_cost: float = 1.0
    cost_basis: datetime
    metadata: Dict[str, Any] = {}

class AllocationPolicy(BaseModel):
    """Allocation policy for resource distribution"""
    policy_id: str
    tenant_id: str
    allocation_strategy: str = "fair"
    max_allocation_per_request: float = 100.0
    min_allocation_per_request: float = 1.0
    priority_rules: Dict[str, int]
    fairness_score: float = 0.5
    metadata: Dict[str, Any] = {}
class QuotaManager(BaseModel):
    """Quota manager for resource limiting"""
    tenant_id: str
    quotas: Dict[str, float]
    current_usage: Dict[str, float]
    reset_period: str = "daily"
    last_reset: datetime
    metadata: Dict[str, Any] = {}
class ComplianceRecord(BaseModel):
    """Compliance record for tenant auditing"""
    record_id: str
    tenant_id: str
    compliance_type: str
    requirement: str
    status: str = "compliant"
    checked_at: datetime
    evidence: Dict[str, Any]
    notes: Optional[str] = None
class MultiTenantManager:
    """Multi-tenant manager for enterprise deployments"""

    def __init__(self, config: Dict[str, Any]):
        self.tenants: Dict[str, Tenant] = {}
        self.resource_pools: Dict[str, ResourcePool] = {}
        self.allocation_policies: Dict[str, AllocationPolicy] = {}
        self.quota_managers: Dict[str, QuotaManager] = {}
        self.compliance_records: Dict[str, List[ComplianceRecord]] = {}
        self.tenant_usage_log: Dict[str, List[Dict[str, Any]]] = {}
        self.is_running = False
        self.config = config

    async def start(self) -> None:
        """Start multi-tenant manager"""
        self.is_running = True
        logger.info("Multi-tenant manager started")

    async def stop(self) -> None:
        """Stop multi-tenant manager"""
        self.is_running = False
        logger.info("Multi-tenant manager stopped")

    def create_tenant(self, tenant_data: Dict[str, Any]) -> str:
        """Create new tenant"""
        tenant_id = tenant_data.get("tenant_id", f"tenant_{uuid.uuid4()}")
        tenant = Tenant(
            tenant_id=tenant_id,
            name=tenant_data.get("name", ""New Tenant"),
            domain=tenant_data.get("domain", f"{tenant_id}.example.com"),
            tier=tenant_data.get("tier", "standard"),
            resources=tenant_data.get("resources", {}),
            limits=tenant_data.get("limits", {}),
            quotas=tenant_data.get("quotas", {}),
            compliance_level=tenant_data.get("compliance_level", "basic"),
            security_policy=tenant_data.get("security_policy", {}),
            settings=tenant_data.get("settings", {}),
            is_active=tenant_data.get("is_active", True),
            created_at=datetime.now()
        )

        self.tenants[tenant_id] = tenant
        logger.info(f"Created tenant {tenant_id}: {tenant.name}")
        return tenant_id

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        return self.tenants.get(tenant_id)

    def update_tenant(self, tenant_id: str, tenant_data: Dict[str, Any]) -> bool:
        """Update tenant"""
        if tenant_id not in self.tenants:
            return False

        tenant = self.tenants[tenant_id]
        # Update tenant attributes
        if "name" in tenant_data:
            tenant.name = tenant_data["name"]
        if "domain" in tenant_data:
            tenant.domain = tenant_data["domain"]
        if "tier" in tenant_data:
            tenant.tier = tenant_data["tier"]
        if "resources" in tenant_data:
            tenant.resources = tenant_data["resources"]
        if "limits" in tenant_data:
            tenant.limits = tenant_data["limits"]
        if "quotas" in tenant_data:
            tenant.quotas = tenant_data["quotas"]
        if "compliance_level" in tenant_data:
            tenant.compliance_level = tenant_data["compliance_level"]
        if "security_policy" in tenant_data:
            tenant.security_policy = tenant_data["security_policy"]
        if "settings" in tenant_data:
            tenant.settings = tenant_data["settings"]
        if "is_active" in tenant_data:
            tenant.is_active = tenant_data["is_active"]

        tenant.last_seen = datetime.now()
        logger.info(f"Updated tenant {tenant_id}")
        return True

    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete tenant"""
        if tenant_id not in self.tenants:
            return False

        del self.tenants[tenant_id]
        # Clean up related resources
        self._cleanup_tenant_resources(tenant_id)
        logger.info(f"Deleted tenant {tenant_id}")
        return True

    def _cleanup_tenant_resources(self, tenant_id: str) -> None:
        """Clean up tenant resources"""
        # Remove tenant resource pools
        pool_keys = [k for k in self.resource_pools.keys() if k.startswith(f"{tenant_id}-")
        for pool_key in pool_keys:
            del self.resource_pools[pool_key]

        # Remove tenant allocation policies
        alloc_keys = [k for k in self.allocation_policies.keys() if k.startswith(f"{tenant_id}-")
        for alloc_key in alloc_keys:
            del self.allocation_policies[alloc_key]

        # Remove tenant quota managers
        quota_keys = [k for k in self.quota_managers.keys() if k.startswith(f"{tenant_id}-")
        for quota_key in quota_keys:
            del self.quota_managers[quota_key]

        # Remove tenant compliance records
        if tenant_id in self.compliance_records:
            del self.compliance_records[tenant_id]

        # Remove tenant usage logs
        if tenant_id in self.tenant_usage_log:
            del self.tenant_usage_log[tenant_id]

    def create_resource_pool(self, pool_data: Dict[str, Any]) -> str:
        """Create resource pool for tenant"""
        pool_id = f"pool_{pool_data.get('tenant_id')}_{pool_data.get('resource_type')}"
        resource_pool = ResourcePool(
            pool_id=pool_id,
            tenant_id=pool_data["tenant_id"],
            resource_type=pool_data["resource_type"],
            total_capacity=pool_data.get("total_capacity", 0.0),
            allocated_capacity=pool_data.get("allocated_capacity", 0.0),
            available_capacity=pool_data.get("available_capacity", pool_data.get("total_capacity", 0.0)),
            unit_cost=pool_data.get("unit_cost", 1.0),
            cost_basis=pool_data.get("cost_basis", datetime.now()),
            metadata=pool_data.get("metadata", {})
        )

        self.resource_pools[pool_id] = resource_pool
        logger.info(f"Created resource pool {pool_id} for tenant {pool_data['tenant_id']}")
        return pool_id

    def get_resource_pool(self, pool_id: str) -> Optional[ResourcePool]:
        """Get resource pool by ID"""
        return self.resource_pools.get(pool_id)

    def allocate_resource(
        self,
        tenant_id: str,
        resource_type: str,
        amount: float
    ) -> Dict[str, Any]:
        """Allocate resources to tenant"""
        try:
            # Find resource pool
            pool_id = f"pool_{tenant_id}_{resource_type}"
            if pool_id not in self.resource_pools:
                return {
                    "success": False,
                    "error": "Resource pool not found",
                    "pool_id": pool_id
                }

            resource_pool = self.resource_pools[pool_id]

            # Check if enough capacity
            if resource_pool.available_capacity < amount:
                return {
                    "success": False,
                    "error": f"Insufficient capacity. Available: {resource_pool.available_capacity}, Requested: {amount}",
                    "pool_id": pool_id,
                    "available": resource_pool.available_capacity
                }

            # Allocate resources
            resource_pool.allocated_capacity += amount
            resource_pool.available_capacity -= amount

            # Record allocation
            await self._record_tenant_usage(
                tenant_id=tenant_id,
                resource_type=resource_type,
                amount=amount,
                pool_id=pool_id
            )

            return {
                "success": True,
                "pool_id": pool_id,
                "allocated": amount,
                "remaining": resource_pool.available_capacity,
                "message": f"Allocated {amount} units of {resource_type} to tenant {tenant_id}"
            }

        except Exception as e:
            logger.error(f"Failed to allocate resources: {e}")
            return {
                "success": False,
                "error": f"Allocation error: {e}",
                "pool_id": pool_id
            }

    def release_resource(
        self,
        tenant_id: str,
        resource_type: str,
        amount: float
    ) -> Dict[str, Any]:
        """Release resources from tenant"""
        try:
            # Find resource pool
            pool_id = f"pool_{tenant_id}_{resource_type}"
            if pool_id not in self.resource_pools:
                return {
                    "success": False,
                    "error": "Resource pool not found",
                    "pool_id": pool_id
                }

            resource_pool = self.resource_pools[pool_id]

            # Check if enough allocated resources
            if resource_pool.allocated_capacity < amount:
                return {
                    "success": False,
                    "error": f"Insufficient allocated resources. Allocated: {resource_pool.allocated_capacity}, Requested: {amount}",
                    "pool_id": pool_id,
                    "allocated": resource_pool.allocated_capacity
                }

            # Release resources
            resource_pool.allocated_capacity -= amount
            resource_pool.available_capacity += amount

            # Record deallocation
            await self._record_tenant_usage(
                tenant_id=tenant_id,
                resource_type=resource_type,
                amount=-amount,
                pool_id=pool_id
            )

            return {
                "success": True,
                "pool_id": pool_id,
                "released": amount,
                "remaining_allocated": resource_pool.allocated_capacity,
                "message": f"Released {amount} units of {resource_type} from tenant {tenant_id}"
            }

        except Exception as e:
            logger.error(f"Failed to release resources: {e}")
            return {
                "success": False,
                "error": f"Release error: {e}",
                "pool_id": pool_id
            }

    async def _record_tenant_usage(
        self,
        tenant_id: str,
        resource_type: str,
        amount: float,
        pool_id: str
    ) -> None:
        """Record tenant resource usage"""
        timestamp = datetime.now()

        usage_record = {
            "timestamp": timestamp,
            "resource_type": resource_type,
            "amount": amount,
            "pool_id": pool_id,
            "tenant_id": tenant_id
        }

        if tenant_id not in self.tenant_usage_log:
            self.tenant_usage_log[tenant_id] = []

        self.tenant_usage_log[tenant_id].append(usage_record)


        # Keep only recent records (last 100)
        if len(self.tenant_usage_log.get(tenant_id, [])) > 100:
            self.tenant_usage_log[tenant_id] = self.tenant_usage_log[tenant_id][-100:]


    def get_tenant_usage(
        self,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        resource_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get tenant usage records"""
        if tenant_id not in self.tenant_usage_log:
            return []

        usage_records = self.tenant_usage_log[tenant_id]

        # Filter by resource type
        if resource_type:
            usage_records = [r for r in usage_records if r["resource_type"] == resource_type]


        # Filter by time range
        if start_time:
            usage_records = [r for r in usage_records if r["timestamp"] >= start_time]
        if end_time:
            usage_records = [r for r in usage_records if r["timestamp"] <= end_time]


        return usage_records

    def get_tenant_resources(
        self,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Get tenant resources summary"""
        tenant_resources = []
        for pool_id, pool in self.resource_pools.items():
            if pool.tenant_id == tenant_id:
                tenant_resources.append({
                    "pool_id": pool_id,
                    "resource_type": pool.resource_type,
                    "total_capacity": pool.total_capacity,
                    "allocated": pool.allocated_capacity,
                    "available": pool.available_capacity,
                    "unit_cost": pool.unit_cost
                })


        return {
            "tenant_id": tenant_id,
            "resources": tenant_resources,
            "total_capacity": sum(r["total_capacity"] for r in tenant_resources),
            "allocated": sum(r["allocated"] for r in tenant_resources),
            "available": sum(r["available"] for r in tenant_resources)
        }

    def create_allocation_policy(self, policy_data: Dict[str, Any]) -> str:
        """Create allocation policy for tenant"""
        policy_id = f"policy_{policy_data.get('tenant_id')}_{policy_data.get('allocation_strategy')}"
        allocation_policy = AllocationPolicy(
            policy_id=policy_id,
            tenant_id=policy_data["tenant_id"],
            allocation_strategy=policy_data.get("allocation_strategy", "fair"),
            max_allocation_per_request=policy_data.get("max_allocation_per_request", 100.0),
            min_allocation_per_request=policy_data.get("min_allocation_per_request", 1.0),
            priority_rules=policy_data.get("priority_rules", {}),
            fairness_score=policy_data.get("fairness_score", 0.5),
            metadata=policy_data.get("metadata", {})
        )


        self.allocation_policies[policy_id] = allocation_policy
        logger.info(f"Created allocation policy {policy_id} for tenant {policy_data['tenant_id']}")
        return policy_id

    def get_allocation_policy(self, policy_id: str) -> Optional[AllocationPolicy]:
        """Get allocation policy by ID"""
        return self.allocation_policies.get(policy_id)


    def create_quota_manager(self, quota_data: Dict[str, Any]) -> str:
        """Create quota manager for tenant"""
        quota_id = f"quota_{quota_data.get('tenant_id')}_{quota_data.get('reset_period')}"
        quota_manager = QuotaManager(
            tenant_id=quota_data["tenant_id"],
            quotas=quota_data.get("quotas", {}),
            current_usage=quota_data.get("current_usage", {}),
            reset_period=quota_data.get("reset_period", "daily"),
            last_reset=quota_data.get("last_reset", datetime.now()),
            metadata=quota_data.get("metadata", {})
        )

        self.quota_managers[quota_id] = quota_manager
        logger.info(f"Created quota manager {quota_id} for tenant {quota_data['tenant_id']}")
        return quota_id

    def get_quota_manager(self, quota_id: str) -> Optional[QuotaManager]:
        """Get quota manager by ID"""
        return self.quota_managers.get(quota_id)


    def create_compliance_record(self, compliance_data: Dict[str, Any]) -> str:
        """Create compliance record"""
        record_id = f"record_{datetime.now().timestamp()}"
        compliance_record = ComplianceRecord(
            record_id=record_id,
            tenant_id=compliance_data["tenant_id"],
            compliance_type=compliance_data["compliance_type"],
            requirement=compliance_data["requirement"],
            status=compliance_data.get("status", "compliant"),
            checked_at=datetime.now(),
            evidence=compliance_data.get("evidence", {}),
            notes=compliance_data.get("notes")
        )

        if compliance_data["tenant_id"] not in self.compliance_records:
            self.compliance_records[compliance_data["tenant_id"]] = []

        self.compliance_records[compliance_data["tenant_id"]].append(compliance_record)
        logger.info(f"Created compliance record {record_id} for tenant {compliance_data['tenant_id']}")
        return record_id

    def get_compliance_records(
        self,
        tenant_id: str,
        compliance_type: Optional[str] = None
    ) -> List[ComplianceRecord]:
        """Get compliance records for tenant"""
        if tenant_id not in self.compliance_records:
            return []

        records = self.compliance_records[tenant_id]

        if compliance_type:
            records = [r for r in records if r["compliance_type"] == compliance_type]


        return records

    async def start(self) -> None:
        """Start multi-tenant manager"""
        self.is_running = True
        logger.info("Multi-tenant manager started")

    async def stop(self) -> None:
        """Stop multi-tenant manager""""
        self.is_running = False
        logger.info("Multi-tenant manager stopped")