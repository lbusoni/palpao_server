import os
import time
from plico.utils.base_runner import BaseRunner
from plico.utils.logger import Logger
from plico.utils.decorator import override
from plico.utils.control_loop import FaultTolerantControlLoop
from palpao_server.mirror_controller.simulated_deformable_mirror import \
    SimulatedDeformableMirror
from palpao_server.mirror_controller.deformable_mirror_controller import \
    DeformableMirrorController
from plico.rpc.zmq_ports import ZmqPorts
from palpao.calibration.calibration_manager import CalibrationManager


__version__= "$Id: runner.py 27 2018-01-27 08:48:07Z lbusoni $"


class Runner(BaseRunner):

    RUNNING_MESSAGE = "Mirror controller is running."

    def __init__(self):
        BaseRunner.__init__(self)


    def _createDeformableMirrorDevice(self):
        mirrorDeviceSection= self.configuration.getValue(
            self.getConfigurationSection(), 'mirror')
        mirrorModel= self.configuration.deviceModel(mirrorDeviceSection)
        if mirrorModel == 'simulatedMEMSMultiDM':
            self._createSimulatedDeformableMirror(mirrorDeviceSection)
        elif mirrorModel == 'simulatedDM':
            self._createSimulatedDeformableMirror(mirrorDeviceSection)
        elif mirrorModel == 'alpaoDM277':
            self._createAlpaoDM277Mirror(mirrorDeviceSection)
        elif mirrorModel == 'piTipTilt':
            self._createPITipTiltMirror(mirrorDeviceSection)
        else:
            raise KeyError('Unsupported mirror model %s' % mirrorModel)


    def _createSimulatedDeformableMirror(self, mirrorDeviceSection):
        dmSerialNumber= self.configuration.getValue(
            mirrorDeviceSection, 'serial_number')
        self._mirror= SimulatedDeformableMirror(dmSerialNumber)


    def _createAlpaoDM277Mirror(self, mirrorDeviceSection):
        assert False, 'Implement me'


    def _createPITipTiltMirror(self, mirrorDeviceSection):
        from palpao_server.mirror_controller.pi_tip_tilt_mirror \
            import PhysikInstrumenteTipTiltMirror
        from pi_gcs.gcs2 import GeneralCommandSet2
        from pi_gcs.tip_tilt_2_axes import TipTilt2Axis

        hostname= self.configuration.getValue(
            mirrorDeviceSection, 'ip_address')
        serialNumber= self.configuration.getValue(mirrorDeviceSection,
                                                  'serial_number')
        cfg= self._calibrationManager.loadPiTipTiltCalibration(
            serialNumber)
        cfg.hostname= hostname
        gcs=GeneralCommandSet2()
        tt=TipTilt2Axis(gcs, cfg)
        tt.setUp()
        self._mirror= PhysikInstrumenteTipTiltMirror(
            serialNumber, tt)


    def _createCalibrationManager(self):
        calibrationRootDir= self.configuration.calibrationRootDir()
        self._calibrationManager= CalibrationManager(calibrationRootDir)


    def _setUp(self):
        self._logger= Logger.of("Deformable Mirror Controller runner")

        self._zmqPorts= ZmqPorts.fromConfiguration(
            self.configuration, self.getConfigurationSection())
        self._replySocket = self.rpc().replySocket(
            self._zmqPorts.SERVER_REPLY_PORT)
        self._statusSocket = self.rpc().publisherSocket(
            self._zmqPorts.SERVER_STATUS_PORT)

        self._logger.notice('reply socket on port %d' %
                            self._zmqPorts.SERVER_REPLY_PORT)
        self._logger.notice('status socket on port %d' %
                            self._zmqPorts.SERVER_STATUS_PORT)

        self._createCalibrationManager()

        self._createDeformableMirrorDevice()

        self._controller= DeformableMirrorController(
            self.name,
            self._zmqPorts,
            self._mirror,
            self._replySocket,
            self._statusSocket,
            self.rpc())


    def _runLoop(self):
        self._logRunning()

        FaultTolerantControlLoop(
            self._controller,
            Logger.of("Deformable Mirror Controller control loop"),
            time,
            0.00001).start()
        self._logger.notice("Terminated")


    @override
    def run(self):
        self._setUp()
        self._runLoop()
        return os.EX_OK


    @override
    def terminate(self, signal, frame):
        self._controller.terminate()