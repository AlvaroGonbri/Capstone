from rest_framework import serializers


class EventoZabbixSerializer(serializers.Serializer):
    """Cuerpo que envía el media type 'SICMA webhook' de Zabbix."""

    # Un macro sin resolver (p. ej. '{EVENT.ID}') no pasa la validación.
    event_id = serializers.RegexField(r'^\d{1,20}$')
    host = serializers.CharField(max_length=200)
    problem = serializers.CharField(max_length=400)
    severity = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    status = serializers.ChoiceField(choices=('PROBLEM', 'RESOLVED'))
    time = serializers.CharField(max_length=50, required=False, allow_blank=True)
