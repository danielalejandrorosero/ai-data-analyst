from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos de la plataforma.

    El SQL generado por el agente (execute_readonly_sql) nunca pasa por este
    ORM ni por las sesiones que crea — ver .claude/rules/security.md.
    """
