import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.membership import Membership, Role
from app.db.models.organization import Organization
from app.db.models.user import User
from app.domain.audit import service as audit_service
from app.domain.auth.schemas import MembershipOut, OrganizationOut, UserOut
from app.domain.auth.security import (
    create_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_membership(
    db: AsyncSession, *, user_id: uuid.UUID, organization_id: uuid.UUID
) -> Membership | None:
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
        )
    )
    return result.scalar_one_or_none()


async def build_user_out(db: AsyncSession, user: User) -> UserOut:
    result = await db.execute(
        select(Membership, Organization.name)
        .join(Organization, Membership.organization_id == Organization.id)
        .where(Membership.user_id == user.id)
    )
    memberships = [
        MembershipOut(
            organization_id=membership.organization_id,
            organization_name=name,
            role=membership.role,
        )
        for membership, name in result.all()
    ]
    return UserOut(id=user.id, email=user.email, status=user.status, memberships=memberships)


async def register(
    db: AsyncSession, *, email: str, password: str, organization_name: str
) -> tuple[UserOut, str]:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyRegisteredError(email)

    user = User(email=email, password_hash=hash_password(password))
    organization = Organization(name=organization_name)
    db.add_all([user, organization])
    await db.flush()

    membership = Membership(user_id=user.id, organization_id=organization.id, role=Role.OWNER)
    db.add(membership)
    await db.flush()

    await audit_service.record_event(
        db,
        organization_id=organization.id,
        actor_id=user.id,
        action="auth.register",
        target=f"user:{user.id}",
    )

    user_out = await build_user_out(db, user)
    await db.commit()

    return user_out, create_access_token(user.id)


async def authenticate(db: AsyncSession, *, email: str, password: str) -> tuple[UserOut, str]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None or user.password_hash is None:
        # Verificamos igual contra un hash dummy: si retornamos de inmediato
        # sin llamar a Argon2id, el tiempo de respuesta delata si el email
        # existe o no (ver security.verify_dummy_password).
        verify_dummy_password(password)
        raise InvalidCredentialsError()

    if not verify_password(password, user.password_hash):
        # Auditamos el intento fallido (RF-004: "eventos relevantes de
        # autenticacion y autorizacion", no solo los exitosos) - solo es
        # posible para usuarios EXISTENTES, porque audit_events siempre
        # requiere organization_id (es tenant-scoped) y un email
        # inexistente no tiene ningun tenant al que asociarlo. Ese caso
        # queda sin auditar, documentado como limite conocido en
        # docs/security/threat-model.md.
        memberships_result = await db.execute(
            select(Membership).where(Membership.user_id == user.id)
        )
        for membership in memberships_result.scalars():
            await audit_service.record_event(
                db,
                organization_id=membership.organization_id,
                actor_id=user.id,
                action="auth.login_failed",
            )
        await db.commit()
        raise InvalidCredentialsError()

    # Un evento de auditoria vive por tenant (audit_events.organization_id) -
    # se registra el login contra cada organizacion de la que es miembro.
    memberships_result = await db.execute(select(Membership).where(Membership.user_id == user.id))
    for membership in memberships_result.scalars():
        await audit_service.record_event(
            db,
            organization_id=membership.organization_id,
            actor_id=user.id,
            action="auth.login",
        )

    user_out = await build_user_out(db, user)
    await db.commit()

    return user_out, create_access_token(user.id)


async def create_organization(db: AsyncSession, *, actor: User, name: str) -> OrganizationOut:
    organization = Organization(name=name)
    db.add(organization)
    await db.flush()

    membership = Membership(user_id=actor.id, organization_id=organization.id, role=Role.OWNER)
    db.add(membership)
    await db.flush()

    await audit_service.record_event(
        db,
        organization_id=organization.id,
        actor_id=actor.id,
        action="organization.create",
        target=f"organization:{organization.id}",
    )
    await db.commit()

    return OrganizationOut(id=organization.id, name=organization.name, role=Role.OWNER)
